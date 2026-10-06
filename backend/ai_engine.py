"""Engine de IA híbrida do SGTI.

Dois providers de inferência selecionáveis:
  - "llm": LLM local externo (via API HTTP compatível com Ollama; ex. llama3.2
    + nomic-embed-text) — comportamento original do projeto. Alias legado
    "ollama" continua aceito e é normalizado para "llm".
  - "local": engine 100% Python, sem LLM externo — embeddings via
    sentence-transformers (torch CPU; aproveita AVX-512 dos servidores) e
    geração determinística por extração dos trechos do RAG + taxonomia de
    alarmes (regex) + templates.

Seleção: por request (campo "provider" no payload) ou ambiente (AI_PROVIDER).

IMPORTANTE: embeddings de providers/models diferentes NÃO são comparáveis
(dimensões e espaços vetoriais distintos). Cada Documento registra o provider
usado na indexação (documento.embed_provider) e a busca filtra apenas trechos
compatíveis — misturar espaços produziria scores sem sentido.
"""
import re
import threading

from fastapi import HTTPException, status
from pathlib import Path
from dotenv import load_dotenv
import os

import llm_client

load_dotenv(Path(__file__).parent.parent / ".env")

VALID_PROVIDERS = ("llm", "local")
# "ollama" é alias legado, normalizado para "llm"
_LEGACY_PROVIDER_ALIASES = {"ollama": "llm"}
DEFAULT_PROVIDER = os.getenv("AI_PROVIDER", "llm").strip().lower()

# Modelo sentence-transformers recomendado para PT-BR em CPU:
# paraphrase-multilingual-MiniLM-L12-v2 (384 dims, ~120MB, rápido com AVX-512).
# Alternativa de maior qualidade: paraphrase-multilingual-mpnet-base-v2 (768 dims).
LOCAL_EMBED_MODEL = os.getenv("LOCAL_EMBED_MODEL", "paraphrase-multilingual-MiniLM-L12-v2")


def resolve_provider(provider: str | None) -> str:
    """Valida e resolve o provider efetivo (request → env AI_PROVIDER)."""
    p = (provider or DEFAULT_PROVIDER).strip().lower()
    p = _LEGACY_PROVIDER_ALIASES.get(p, p)
    if p not in VALID_PROVIDERS:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Provider '{p}' inválido. Opções: {', '.join(VALID_PROVIDERS)}.",
        )
    return p


def provider_signature(provider: str | None) -> str:
    """Assinatura do espaço vetorial: '<provider>:<modelo>'. Gravada em
    documento.embed_provider — embeddings só são comparados entre assinaturas
    iguais."""
    p = resolve_provider(provider)
    return f"{p}:nomic-embed-text" if p == "llm" else f"{p}:{LOCAL_EMBED_MODEL}"


# ============================================================
# Embeddings locais (sentence-transformers, lazy singleton)
# ============================================================

_local_model = None
_local_model_lock = threading.Lock()


def _get_local_model():
    global _local_model
    if _local_model is None:
        with _local_model_lock:
            if _local_model is None:
                try:
                    from sentence_transformers import SentenceTransformer
                except ImportError as exc:
                    raise HTTPException(
                        status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                        detail=(
                            "provider 'local' exige sentence-transformers instalado "
                            f"({exc}). Instale torch CPU + sentence-transformers."
                        ),
                    ) from exc
                _local_model = SentenceTransformer(LOCAL_EMBED_MODEL, device="cpu")
    return _local_model


def local_embed(texts: list[str]) -> list[list[float]]:
    """Embeddings locais normalizados (cosseno == produto escalar)."""
    if not texts:
        return []
    model = _get_local_model()
    vetores = model.encode(
        texts,
        batch_size=32,
        normalize_embeddings=True,
        convert_to_numpy=True,
        show_progress_bar=False,
    )
    return [v.tolist() for v in vetores]


def local_embed_one(text: str) -> list[float]:
    return local_embed([text])[0]


def embed_one(text: str, provider: str | None = None) -> list[float]:
    if resolve_provider(provider) == "local":
        return local_embed_one(text)
    return llm_client.embed_one(text)


def embed(texts: list[str], provider: str | None = None) -> list[list[float]]:
    if resolve_provider(provider) == "local":
        return local_embed(texts)
    return llm_client.embed(texts)


def cosine_similarity(a: list[float], b: list[float]) -> float:
    """Similaridade cosseno pura em Python (sem numpy), usada na busca vetorial."""
    dot = 0.0
    norm_a = 0.0
    norm_b = 0.0
    for x, y in zip(a, b):
        dot += x * y
        norm_a += x * x
        norm_b += y * y
    if norm_a == 0.0 or norm_b == 0.0:
        return 0.0
    return dot / ((norm_a ** 0.5) * (norm_b ** 0.5))


# ============================================================
# Geração local determinística (substitui o LLM)
# ============================================================

TAXONOMIA_ALARMES: list[tuple[re.Pattern, dict]] = [
    (
        re.compile(
            r"disk|filesystem|file\s*system|storage|parti[çc][ãa]o|espa[çc]o"
            r"|/(?:var|opt|tmp|log)|vhd|vmdk|lvm",
            re.IGNORECASE,
        ),
        {
            "categoria": "disco",
            "diagnostico": "uso/espaço de disco acima do limite em uma ou mais partições.",
            "acoes": [
                "identificar a partição com `df -h`",
                "listar arquivos grandes (`du -xh / | sort -h | tail -30`)",
                "limpar/truncar logs antigos e rotacionar (logrotate)",
                "considerar ampliar a partição se for recorrente",
            ],
            "equipe": "equipe de infraestrutura responsável pelo SO",
        },
    ),
    (
        re.compile(r"cpu|load\s*average|processador|carga\s+alta", re.IGNORECASE),
        {
            "categoria": "cpu",
            "diagnostico": "carga de CPU sustentada acima do limite do host.",
            "acoes": [
                "identificar processos com `top -bn1` ou `pidstat`",
                "verificar se há processo atípico/loop e avaliar limitar prioridade",
                "correlacionar com janelas de carga conhecidas (batch/jobs)",
            ],
            "equipe": "equipe responsável pela aplicação ou SO",
        },
    ),
    (
        re.compile(r"memory|mem[óo]ria|swap|oom|\bram\b", re.IGNORECASE),
        {
            "categoria": "memória",
            "diagnostico": "consumo de memória/swap acima do limite; risco de OOM killer.",
            "acoes": [
                "verificar maiores consumidores (`ps aux --sort=-%mem`)",
                "checar mensagens OOM no dmesg/journal",
                "avaliar limites de memória da aplicação e reinício controlado",
            ],
            "equipe": "equipe responsável pela aplicação ou SO",
        },
    ),
    (
        re.compile(
            r"net(?:if|work)|interface|packet|crc|bandwidth|latency|ping"
            r"|rede|tr[áa]fego|colis[ãa]o",
            re.IGNORECASE,
        ),
        {
            "categoria": "rede",
            "diagnostico": "degradação/falha em interface ou rede (erros, tráfego ou latência).",
            "acoes": [
                "checar contadores da interface (`ip -s link`) e erros CRC",
                "verificar link/switch e cablagem; testar conectividade ao destino",
                "correlacionar com outros hosts da mesma conexão",
            ],
            "equipe": "equipe de redes",
        },
    ),
    (
        re.compile(
            r"service(?:s)?\s+(?:is\s+)?(?:down|not|stop|fail)|systemd|unit\s"
            r"|servi[çc]o\s+(?:parado|fora|indispon)|zabbix\s*agent|\bdown\b",
            re.IGNORECASE,
        ),
        {
            "categoria": "serviço",
            "diagnostico": "serviço/unidade de sistema parado ou não respondendo.",
            "acoes": [
                "verificar status do serviço (`systemctl status <unidade>`)",
                "avaliar logs da unidade (`journalctl -u <unidade> -n 100`)",
                "reiniciar serviço conforme procedimento do manual; se recorrente, escalar",
            ],
            "equipe": "equipe responsável pelo serviço/aplicação",
        },
    ),
    (
        re.compile(r"certificate|ssl|tls|expir|vencid|certificado", re.IGNORECASE),
        {
            "categoria": "certificado",
            "diagnostico": "certificado SSL/TLS a vencer ou vencido.",
            "acoes": [
                "confirmar validade (`openssl s_client -connect host:443 | openssl x509 -dates`)",
                "renovar/reemitir conforme autoridade da organização",
                "validar cadeia e reiniciar o serviço após a troca",
            ],
            "equipe": "equipe de infraestrutura/segurança",
        },
    ),
    (
        re.compile(
            r"postgres|mysql|oracle|sql\s*server|mariadb|database|banco\s+de\s+dados",
            re.IGNORECASE,
        ),
        {
            "categoria": "banco de dados",
            "diagnostico": "problema em SGBD (conexões, locks, replicação ou uso de recursos).",
            "acoes": [
                "checar log do SGBD e conexões ativas",
                "verificar locks/replicação conforme o SGBD",
                "avaliar impacto nas aplicações dependentes antes de reiniciar",
            ],
            "equipe": "equipe de banco de dados (DBA)",
        },
    ),
]

# Limite do trecho citado na resposta local (evita resposta quilométrica)
_LIMITE_CITACAO = 700


def _classificar(texto: str) -> dict | None:
    texto = texto or ""
    for regex, perfil in TAXONOMIA_ALARMES:
        if regex.search(texto):
            return perfil
    return None


def local_alarm_analysis(
    alarme: dict,
    contexto_cmdb: dict,
    trechos: list[dict],
) -> str:
    """Análise determinística de alarme Zabbix (mesma estrutura do prompt do LLM).

    alarme: {event_id, host, problema, severidade, mensagem}
    """
    texto_alarme = " ".join(
        str(alarme.get(campo) or "") for campo in ("problema", "mensagem")
    )
    perfil = _classificar(texto_alarme)
    ativo = (contexto_cmdb or {}).get("ativo") or {}
    relacionamentos = (contexto_cmdb or {}).get("relacionamentos") or []
    criticidade = ativo.get("criticidade") or "não informada"
    sev = (alarme.get("severidade") or "").strip()

    # (1) Diagnóstico
    if perfil:
        diag = f"provável problema de {perfil['categoria']}: {perfil['diagnostico']}"
    else:
        diag = (
            "não classificado automaticamente pela taxonomia local (nome do problema: "
            f"\"{(alarme.get('problema') or '—').strip()}\")"
        )

    # (3) Ação recomendada — prioridade ao procedimento recuperado por RAG
    acao_parts: list[str] = []
    if trechos:
        melhor = trechos[0]
        citacao = melhor["conteudo"].strip()
        if len(citacao) > _LIMITE_CITACAO:
            citacao = citacao[:_LIMITE_CITACAO].rsplit(" ", 1)[0] + "…"
        secao = f" § {melhor['titulo_secao']}" if melhor.get("titulo_secao") else ""
        acao_parts.append(
            f"Procedimento documentado [{melhor['documento']}{secao}, "
            f"score {melhor['score']:.2f}]:\n{citacao}"
        )
    elif perfil:
        acao_parts.append("Ações padrão da categoria: " + "; ".join(perfil["acoes"]) + ".")
    else:
        acao_parts.append("Nenhum procedimento documentado recuperado — tratar caso a caso.")

    # (2) Impacto — CMDB
    impacto_parts = [
        f"ativo: {ativo.get('nome') or alarme.get('host') or '—'}"
        f" | ambiente: {ativo.get('ambiente') or '—'}"
        f" | criticidade CMDB: {criticidade}"
    ]
    if ativo.get("aplicacoes"):
        impacto_parts.append(f"aplicações hospedadas: {', '.join(ativo['aplicacoes'])}")
    if relacionamentos:
        deps = ", ".join(rel.get("outro_ativo", "?") for rel in relacionamentos[:6])
        impacto_parts.append(f"{len(relacionamentos)} dependência(s) no CMDB: {deps}")
    if sev:
        impacto_parts.append(f"severidade do alarme: {sev}")

    # (4) Escalação
    parts_escalacao: list[str] = []
    if perfil:
        parts_escalacao.append(f"escalar para {perfil['equipe']}")
    if criticidade.lower() in ("crítica", "critica", "alta") or sev.lower() in (
        "high", "disaster", "average",
    ):
        parts_escalacao.append("severidade/criticidade elevada — tratamento imediato")
    if not trechos:
        parts_escalacao.append("sem procedimento documentado — escalar à equipe responsável")
    escalacao = "; ".join(parts_escalacao) if parts_escalacao else "conforme procedimento acima"

    rodape = (
        "Fonte: engine local determinística (sem LLM); análise baseada em CMDB + base de conhecimento."
        if trechos
        else "Fonte: engine local determinística (sem LLM); nenhum trecho recuperado da base de conhecimento."
    )

    linhas = [
        f"(1) Diagnóstico provável: {diag}",
        f"(2) Impacto e criticidade: {' | '.join(impacto_parts)}",
        f"(3) Ação recomendada: {' '.join(acao_parts)}",
        f"(4) Escalação: {escalacao}",
        rodape,
    ]
    return "\n\n".join(linhas)


def local_rag_answer(pergunta: str, trechos: list[dict]) -> str:
    """Resposta extrativa do RAG: cita os melhores trechos literalmente.

    Sem LLM não há paraphrase — a resposta é o conteúdo real dos manuais,
    o que elimina risco de alucinação e preserva rastreabilidade."""
    if not trechos:
        return (
            "Nenhum trecho da base de conhecimento corresponde à consulta. "
            "Não há procedimento documentado recuperável — escale para a equipe responsável."
        )
    linhas = ["Resposta extraída da base de conhecimento (engine local, sem LLM):"]
    for i, trecho in enumerate(trechos, start=1):
        citacao = trecho["conteudo"].strip()
        if len(citacao) > _LIMITE_CITACAO:
            citacao = citacao[:_LIMITE_CITACAO].rsplit(" ", 1)[0] + "…"
        secao = f" § {trecho['titulo_secao']}" if trecho.get("titulo_secao") else ""
        linhas.append(f"[{i}] {trecho['documento']}{secao} (score {trecho['score']:.2f})")
        linhas.extend(f"    {linha}" for linha in citacao.splitlines() if linha)
    linhas.append(
        "Se as informações acima não resolverem, escale para a equipe responsável "
        "pelo serviço afetado."
    )
    return "\n".join(linhas)


def local_generate(question: str) -> str:
    """Resposta determinística para endpoints de geração livre (sem DB/RAG).

    Classifica a pergunta na taxonomia e devolve orientação padrão; indica
    explicitamente que a engine local não usa LLM."""
    perfil = _classificar(question)
    if perfil:
        return (
            "[Engine local, sem LLM] Classificação: "
            f"{perfil['categoria']} — {perfil['diagnostico']}\n"
            "Orientação padrão: " + " ".join(perfil["acoes"]) + "\n"
            "Para resposta com base nos manuais, use os endpoints de RAG/alarmes "
            "com a base de conhecimento indexada."
        )
    return (
        "[Engine local, sem LLM] Não foi possível classificar a consulta na taxonomia "
        "local de alarmes. O RAG (`/ia/knowledge/*`) responde com extração literal "
        "dos manuais indexados — consulte-o ou reformule a consulta com termos técnicos."
    )


def local_chunk_stream(texto: str, tamanho: int = 80):
    """Fatia o texto local em chunks para simular streaming NDJSON do RAG."""
    for i in range(0, len(texto), tamanho):
        yield texto[i:i + tamanho]