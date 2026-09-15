"""Base de conhecimento RAG: indexação de Markdown + busca vetorial (nomic-embed-text)."""
import hashlib
import logging
import os
import re
import time
from pathlib import Path

from sqlalchemy.orm import Session

import models
import ollama

logger = logging.getLogger(__name__)

CHUNK_SIZE = 900
CHUNK_OVERLAP = 150
MAX_CHUNK_CHARS = 1600

HEADING_RE = re.compile(r"^(#{1,6})\s+(.+)$", re.MULTILINE)


def knowledge_dir() -> Path:
    return Path(os.getenv("KNOWLEDGE_DIR", "./knowledge")).expanduser()


def _limpar_markdown(texto: str) -> str:
    texto = re.sub(r"```[a-zA-Z0-9_-]*\n(.*?)```", r"\1", texto, flags=re.DOTALL)
    texto = re.sub(r"!\[[^\]]*\]\([^)]*\)", "", texto)
    texto = re.sub(r"\[([^\]]+)\]\([^)]*\)", r"\1", texto)
    texto = re.sub(r"^\s{0,3}>\s?", "", texto, flags=re.MULTILINE)
    texto = re.sub(r"^(\s*)[-*+]\s+", r"\1", texto, flags=re.MULTILINE)
    texto = re.sub(r"^(\s*)\d+\.\s+", r"\1", texto, flags=re.MULTILINE)
    texto = re.sub(r"[*_`]{1,3}", "", texto)
    texto = re.sub(r"\n{3,}", "\n\n", texto)
    return texto.strip()


def chunk_markdown(texto: str) -> list[dict]:
    """Divide o Markdown em trechos por seção (headings), com fallback por tamanho."""
    headings = [(m.start(), m.group(1), m.group(2).strip()) for m in HEADING_RE.finditer(texto)]
    if not headings:
        boundaries = [(0, "", "")]
    else:
        boundaries = [(0, "", "")]
        boundaries.extend((pos, hashes, title) for pos, hashes, title in headings)
        boundaries.append((len(texto), "", ""))

    trechos: list[dict] = []
    for i in range(len(boundaries) - 1):
        start, hashes, title = boundaries[i]
        end = boundaries[i + 1][0]
        conteudo = _limpar_markdown(texto[start:end])
        if not conteudo:
            continue
        for parte in _fatia_com_overlap(conteudo):
            trechos.append({"titulo_secao": title or None, "conteudo": parte})
    return trechos


def _fatia_com_overlap(texto: str) -> list[str]:
    if len(texto) <= MAX_CHUNK_CHARS:
        return [texto]
    partes: list[str] = []
    start = 0
    while start < len(texto):
        fim = min(start + CHUNK_SIZE, len(texto))
        if fim < len(texto):
            quebra = texto.find("\n", fim - CHUNK_OVERLAP, fim + CHUNK_OVERLAP)
            if quebra != -1:
                fim = quebra + 1
        partes.append(texto[start:fim].strip())
        if fim >= len(texto):
            break
        start = max(fim - CHUNK_OVERLAP, start + 1)
    return [p for p in partes if p]


def _hash_arquivo(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def index_directory(db: Session, diretorio: str | None = None, recriar: bool = False) -> dict:
    """Varre o diretório de Markdown, gera embeddings e persiste documentos/trechos."""
    inicio = time.time()
    base = Path(diretorio).expanduser() if diretorio else knowledge_dir()
    if not base.is_dir():
        raise FileNotFoundError(f"Diretório de conhecimento não encontrado: {base}")

    arquivos = sorted(p for p in base.rglob("*.md") if p.is_file())
    if recriar:
        removidos = db.query(models.Documento).delete()
        db.flush()
    else:
        removidos = 0

    indexados = 0
    total_trechos = 0
    for arquivo in arquivos:
        nome = arquivo.stem
        caminho = str(arquivo.resolve())
        conteudo = arquivo.read_text(encoding="utf-8", errors="replace")
        conteudo_hash = _hash_arquivo(arquivo)

        existente = db.query(models.Documento).filter(models.Documento.nome == nome).one_or_none()
        if existente:
            if existente.conteudo_hash == conteudo_hash:
                total_trechos += db.query(models.TrechoDocumento).filter(
                    models.TrechoDocumento.documento_id == existente.id
                ).count()
                continue
            db.delete(existente)
            db.flush()

        trechos_texto = chunk_markdown(conteudo)
        if not trechos_texto:
            continue

        embeddings = ollama.embed(
            [t["conteudo"] for t in trechos_texto],
        )

        doc = models.Documento(
            nome=nome,
            arquivo=caminho,
            titulo=nome.replace("-", " ").replace("_", " ").title(),
            conteudo_hash=conteudo_hash,
        )
        db.add(doc)
        db.flush()

        for ordem, (trecho, vetor) in enumerate(zip(trechos_texto, embeddings)):
            db.add(
                models.TrechoDocumento(
                    documento_id=doc.id,
                    ordem=ordem,
                    titulo_secao=trecho["titulo_secao"],
                    conteudo=trecho["conteudo"],
                    embedding=vetor,
                )
            )
        db.commit()
        indexados += 1
        total_trechos += len(trechos_texto)
        logger.info(
            "Documento indexado",
            extra={"documento": nome, "trechos": len(trechos_texto), "arquivo": caminho},
        )

    return {
        "arquivos_encontrados": len(arquivos),
        "documentos_indexados": indexados,
        "trechos_indexados": total_trechos,
        "documentos_removidos": removidos,
        "duracao_segundos": round(time.time() - inicio, 2),
    }


def search(db: Session, query: str, top_k: int = 5) -> list[dict]:
    """Busca semântica: embedding da query vs. embeddings dos trechos (cosseno)."""
    trechos = (
        db.query(models.TrechoDocumento)
        .join(models.Documento)
        .all()
    )
    if not trechos:
        return []

    vetor_query = ollama.embed_one(query)
    resultados: list[tuple[float, models.TrechoDocumento]] = []
    for trecho in trechos:
        score = ollama.cosine_similarity(vetor_query, trecho.embedding)
        resultados.append((score, trecho))
    resultados.sort(key=lambda par: par[0], reverse=True)

    return [
        {
            "documento": trecho.documento.titulo or trecho.documento.nome,
            "arquivo": trecho.documento.arquivo,
            "titulo_secao": trecho.titulo_secao,
            "score": round(score, 4),
            "conteudo": trecho.conteudo,
        }
        for score, trecho in resultados[:top_k]
    ]


RAG_SYSTEM_PROMPT = (
    "Você é um assistente técnico de NOC/NOC-SOC do SGTI que auxilia analistas de monitoramento. "
    "Responda SEMPRE em português do Brasil, de forma objetiva e acionável. "
    "Use SOMENTE as informações dos trechos de manuais e procedimentos fornecidos no contexto. "
    "Se a informação não estiver no contexto, diga explicitamente que não há procedimento documentado "
    "e sugira escalar para a equipe responsável. Cite os nomes dos documentos usados."
)

RAG_USER_TEMPLATE = (
    "Trechos relevantes dos manuais/procedimentos (RAG):\n"
    "{contexto}\n\n"
    "Pergunta/alarme:\n{pergunta}\n\n"
    "Instruções: responda com (1) diagnóstico provável, (2) ação recomendada passo a passo, "
    "(3) quando escalar e para quem. Seja direto."
)


def build_context(trechos: list[dict], max_chars: int = 12000) -> str:
    partes: list[str] = []
    total = 0
    for i, trecho in enumerate(trechos, start=1):
        bloco = (
            f"[{i}] Documento: {trecho['documento']} | Seção: {trecho.get('titulo_secao') or '—'} "
            f"| score={trecho['score']}\n{trecho['conteudo']}\n"
        )
        if total + len(bloco) > max_chars:
            break
        partes.append(bloco)
        total += len(bloco)
    return "\n".join(partes)


def answer_question(
    db: Session,
    pergunta: str,
    top_k: int = 5,
    chat_model: str | None = None,
    embed_model: str | None = None,
) -> dict:
    trechos = search(db, pergunta, top_k)
    contexto = build_context(trechos)
    prompt = RAG_USER_TEMPLATE.format(contexto=contexto or "(nenhum trecho recuperado)", pergunta=pergunta)
    resposta = ollama.chat(prompt, model=chat_model, system=RAG_SYSTEM_PROMPT)
    return {"pergunta": pergunta, "resposta": resposta, "trechos": trechos}