"""Inferência de mapa de TI assistida por IA (Ollama llama3.2).

Variante de infer_infra_map.py que troca o dicionário lexical e os padrões
regex por um LLM local, mantendo o mesmo contrato com a API do backend
(service token, idempotente, --dry-run).

Pipeline:
  0. Coleta ativos e aplicações via API + checagem dos modelos no Ollama
  1. Serviços por ativo      → LLM em lote (JSON estruturado, com confiabilidade)
  2. Match ativo ↔ aplicação → pré-filtro por embeddings (nomic-embed-text,
     similaridade cosseno) + LLM só nos K melhores candidatos de cada ativo
  3. Agrupamento de apps     → area_negocio + LLM dá o nome do serviço de negócio
  4. Relacionamentos:
     4a. técnicos determinísticos (multi-host → Replica para; banco declarado
         + host do SGBD → Depende de) — reutiliza a lógica do script lexical
     4b. dependências citadas em objetivo/descrição → LLM avalia cada app
         contra a lista de nomes das demais
  5. Reconciliação: cada ação executada é reportada à API com a confiabilidade
     devolvida pelo modelo; ações com confiabilidade abaixo do limiar
     (--limiar-confianca, padrão 0.9) abrem itens pendentes de verificação
     manual por 2+ analistas no painel de Reconciliações (fonte 'ia').

Todos os POSTs passam pela API oficial (audit log). Reexecução não duplica.
Erros do Ollama não abortam o pipeline: a etapa que falha é pulada com aviso
e as demais etapas determinísticas continuam.

Uso:
  cd backend && ../venv/bin/python infer_infra_map_ia.py --api http://localhost:8000 \
      --token <service-token> [--dry-run] [--verbose]
      [--ollama http://localhost:11434] [--chat-model llama3.2]
      [--embed-model nomic-embed-text] [--top-k 5] [--limiar 0.35]
      [--lote-servicos 40] [--limiar-confianca 0.9] [--sem-ia]
"""
import argparse
import json
import re
import sys
import time
import unicodedata
from collections import defaultdict
from urllib import error, parse, request

# ============================================================
# Cliente Ollama (mesmo estilo do backend/ollama.py, sem HTTPException)
# ============================================================

CHAT_MODES_VALIDOS = ('database', 'appserver', 'erp', 'integration', 'gateway',
                      'directory', 'scheduler', 'metadata', 'data-portal',
                      'security', 'web', 'cache', 'fila', 'outro')


class OllamaError(Exception):
    pass


class Ollama:
    def __init__(self, base: str, chat_model: str, embed_model: str, keep_alive: str = '30m'):
        self.base = base.rstrip('/')
        self.chat_model = chat_model
        self.embed_model = embed_model
        self.keep_alive = keep_alive

    def _post(self, path: str, payload: dict, timeout: int = 600):
        req = request.Request(f'{self.base}{path}', data=json.dumps(payload).encode(),
                              headers={'Content-Type': 'application/json'}, method='POST')
        try:
            with request.urlopen(req, timeout=timeout) as resp:
                return json.loads(resp.read().decode('utf-8'))
        except error.HTTPError as e:
            raise OllamaError(f'HTTP {e.code} do Ollama: {e.read().decode(errors="replace")[:200]}') from e
        except (error.URLError, TimeoutError, ConnectionError) as e:
            raise OllamaError(f'Falha ao conectar ao Ollama: {e}') from e

    def _get(self, path: str, timeout: int = 15):
        req = request.Request(f'{self.base}{path}', method='GET')
        try:
            with request.urlopen(req, timeout=timeout) as resp:
                return json.loads(resp.read().decode('utf-8'))
        except (error.URLError, error.HTTPError, TimeoutError, ConnectionError) as e:
            raise OllamaError(f'Falha ao consultar {path} no Ollama: {e}') from e

    def modelos(self) -> list[str]:
        return [m.get('name', '') for m in self._get('/api/tags').get('models', [])]

    def tem_modelos(self) -> tuple[bool, str]:
        """Confirma que chat e embed estão instalados (nome base ou com :tag)."""
        try:
            nomes = self.modelos()
        except OllamaError as e:
            return False, str(e)
        faltando = []
        for alvo in (self.chat_model, self.embed_model):
            if not any(n == alvo or n.split(':')[0] == alvo for n in nomes):
                faltando.append(alvo)
        if faltando:
            return False, 'modelos ausentes no Ollama: ' + ', '.join(faltando)
        return True, ''

    def chat_json(self, system: str, user: str, temperatura: float = 0.1,
                  tentativas: int = 3) -> dict:
        """Chat não-stream com resposta forçada em JSON (format=json) + retry."""
        payload = {
            'model': self.chat_model,
            'messages': [{'role': 'system', 'content': system},
                         {'role': 'user', 'content': user}],
            'stream': False,
            'keep_alive': self.keep_alive,
            'format': 'json',
            'options': {'temperature': temperatura, 'num_ctx': 8192},
        }
        ultimo: Exception | None = None
        for _ in range(tentativas):
            try:
                data = self._post('/api/chat', payload)
                content = (data.get('message') or {}).get('content') or '{}'
                try:
                    return json.loads(content)
                except json.JSONDecodeError:
                    m = re.search(r'\{.*\}', content, re.S)
                    return json.loads(m.group(0)) if m else {}
            except OllamaError as e:
                ultimo = e
                time.sleep(2)
        raise OllamaError(f'chat_json falhou após {tentativas} tentativas: {ultimo}')

    def embed(self, texts: list[str]) -> list[list[float]]:
        out = []
        for i in range(0, len(texts), 32):
            lote = texts[i:i + 32]
            data = self._post('/api/embed', {'model': self.embed_model, 'input': lote,
                                             'keep_alive': self.keep_alive})
            embs = data.get('embeddings')
            if not embs or len(embs) != len(lote):
                raise OllamaError('resposta /api/embed inválida ou incompleta')
            out.extend(embs)
        return out


def cos_sim(a: list[float], b: list[float]) -> float:
    dot = na = nb = 0.0
    for x, y in zip(a, b):
        dot += x * y
        na += x * x
        nb += y * y
    if na == 0.0 or nb == 0.0:
        return 0.0
    return dot / ((na ** 0.5) * (nb ** 0.5))


def _confianca(valor, padrao: float = 0.0) -> float:
    """Normaliza a confiabilidade devolvida pelo LLM para 0.0..1.0.

    Aceita 0..1 ou 0..100 (escala percentual); inválido/ausente → padrao."""
    try:
        c = float(valor)
    except (TypeError, ValueError):
        return padrao
    if c > 1.0:
        c /= 100.0
    return max(0.0, min(1.0, c))

# ============================================================
# Cliente da API do backend (idêntico ao infer_infra_map.py)
# ============================================================

class Api:
    def __init__(self, base: str, token: str):
        self.base = base.rstrip('/')
        self.token = token

    def _req(self, method: str, path: str, body: dict | None = None):
        url = f'{self.base}{path}'
        data = json.dumps(body).encode() if body is not None else None
        req = request.Request(url, data=data, method=method, headers={
            'X-Service-Token': self.token,
            'Content-Type': 'application/json',
        })
        with request.urlopen(req, timeout=30) as resp:
            payload = resp.read()
            return resp.status, json.loads(payload) if payload else None

    def get(self, path: str):
        return self._req('GET', path)[1]

    def post(self, path: str, body: dict):
        return self._req('POST', path, body)


def api_get_all(api: Api, path: str, params: dict | None = None, paginated: bool = True) -> list:
    q = parse.urlencode(dict(params or {}))
    if not paginated:
        return api.get(f'{path}?{q}' if q else path)
    out, skip, limit = [], 0, 100
    while True:
        q = dict(params or {})
        q.update({'skip': skip, 'limit': limit})
        page = api.get(f'{path}?{parse.urlencode(q)}')
        if not page:
            break
        out.extend(page)
        if len(page) < limit:
            break
        skip += limit
    return out


def norm(txt: str) -> str:
    txt = unicodedata.normalize('NFD', (txt or '').lower())
    return ''.join(c for c in txt if unicodedata.category(c) != 'Mn')

# ============================================================
# Etapa 1: serviços por ativo (LLM em lotes)
# ============================================================

SISTEMA_SERVICO = """Você é um analista de CMDB. Para cada ativo (servidor) da lista,
identifique no máximo UM serviço principal de TI que roda nele, com base no nome e
descrição. Responda APENAS com JSON no formato:
{"servicos": [{"ativo": "<nome exato do ativo>", "servico": "<nome normalizado do serviço>", "tipo": "<database|appserver|erp|integration|gateway|directory|scheduler|metadata|data-portal|security|web|cache|fila|outro>", "confianca": <0..1>}]}
Regras: nome do serviço em português/inglês padrão de mercado (ex.: "Apache NiFi",
"Protheus AppServer", "Cassandra", "IBM DataPower"). confianca é sua confiabilidade
na existência daquele serviço naquele ativo (1.0 = certeza). Se nada estiver claro,
omita o ativo. Não invente serviços que não têm evidência no texto."""


def infer_servicos_ia(ativos: list[dict], ol: Ollama, lote: int = 40,
                      verbose: bool = False) -> dict[int, list[tuple[str, str, float]]]:
    """LLM em lotes de ativos; schema impõe UNIQUE(ativo_id) → 1 serviço/ativo.

    Cada serviço vem acompanhado da confiabilidade (0..1) reportada pelo modelo."""
    nome_por_id = {a['nome']: a['id'] for a in ativos}
    resultado: dict[int, list[tuple[str, str, float]]] = {}
    for i in range(0, len(ativos), lote):
        chunk = ativos[i:i + lote]
        linhas = [f"- {a['nome']}: {(a.get('descricao') or '')[:300]}" for a in chunk]
        resp = ol.chat_json(SISTEMA_SERVICO, '\n'.join(linhas))
        resolvidos = 0
        for item in resp.get('servicos', []) or []:
            srv = (item.get('servico') or '').strip()
            tipo = (item.get('tipo') or 'outro').strip().lower()
            conf = _confianca(item.get('confianca'))
            if not srv:
                continue
            if tipo not in CHAT_MODES_VALIDOS:
                tipo = 'outro'
            aid = nome_por_id.get(item.get('ativo') or '') or next(
                (id for nome, id in nome_por_id.items() if norm(nome) == norm(item.get('ativo') or '')), None)
            if aid is None:
                continue
            resultado[aid] = [(srv, tipo, conf)]
            resolvidos += 1
        if verbose:
            print(f'  lote {i // lote + 1}: {resolvidos} serviços identificados')
    return resultado

# ============================================================
# Etapa 2: match ativo ↔ aplicação (embeddings + LLM nos top-K)
# ============================================================

TEXTO_APP = 'sistema: {s}\ndescrição: {d}\nobjetivo: {o}\nlinguagens: {l}\nbancos: {b}'


def _texto_app(app: dict) -> str:
    return TEXTO_APP.format(s=app.get('sistema', ''), d=app.get('descricao') or '',
                            o=(app.get('objetivo') or '')[:300], l=app.get('linguagens') or '',
                            b=app.get('bancos_dados') or '')


def _texto_ativo(a: dict, servicos: list[tuple[str, str, float]]) -> str:
    srv = '; '.join(f'{n} ({t})' for n, t, _ in servicos) if servicos else 'nenhum serviço inferido'
    return f"hostname: {a['nome']} | descrição: {(a.get('descricao') or '')[:300]} | serviços: {srv}"


SISTEMA_MATCH = """Você valida se uma aplicação roda em um servidor, com base nas descrições.
Responda APENAS JSON: {"match": true|false, "confianca": <0..1>, "motivo": "<até 10 palavras>"}
Regra: true somente se houver evidência clara de que a aplicação/sistema é hospedado ou executado
naquele servidor. Palavras genéricas ("sistema", "servidor", "portal") não contam como evidência."""


def infer_instancias_ia(ativos: list[dict], apps: list[dict], servicos_por_ativo: dict,
                        ol: Ollama, top_k: int, limiar: float, verbose: bool) -> list[tuple[dict, dict, str, float]]:
    # pré-filtro vetorial: candidatos por similaridade cosseno
    corpus_ativo = {a['id']: _texto_ativo(a, servicos_por_ativo.get(a['id'], [])) for a in ativos}
    corpus_app = {app['id']: _texto_app(app) for app in apps}
    ids_a = list(corpus_ativo)
    ids_p = list(corpus_app)
    vetores_a = ol.embed([corpus_ativo[i] for i in ids_a])
    vetores_p = ol.embed([corpus_app[i] for i in ids_p])

    candidatos: dict[int, list[tuple[int, float]]] = {}
    for ia, va in zip(ids_a, vetores_a):
        sims = []
        for ip, vp in zip(ids_p, vetores_p):
            s = cos_sim(va, vp)
            if s >= limiar:
                sims.append((ip, s))
        sims.sort(key=lambda x: -x[1])
        candidatos[ia] = sims[:top_k]

    total_cand = sum(len(v) for v in candidatos.values())
    if verbose:
        print(f'  pré-filtro vetorial: {total_cand} candidatos (limiar {limiar}, top {top_k})')

    app_por_id = {app['id']: app for app in apps}
    pares = []
    for a in ativos:
        for app_id, s in candidatos.get(a['id'], []):
            app = app_por_id[app_id]
            prompt = (f'APLICAÇÃO\n{_texto_app(app)}\n\nSERVIDOR\n{_texto_ativo(a, servicos_por_ativo.get(a["id"], []))}')
            resp = ol.chat_json(SISTEMA_MATCH, prompt)
            if resp.get('match') is True:
                conf = _confianca(resp.get('confianca'), padrao=s)
                if conf >= 0.6:
                    motivo = (resp.get('motivo') or f'similaridade {s:.2f}').strip()[:60]
                    pares.append((a, app, f'{motivo} (sim {s:.2f})', conf))
    return pares

# ============================================================
# Etapa 3: serviços de negócio (agrupamento por área + nome via LLM)
# ============================================================

SISTEMA_GRUPO = """Dada uma lista de aplicações da mesma área de negócio, proponha UM nome
curto de serviço de negócio que as represente. Responda APENAS JSON:
{"nome": "<até 5 palavras>", "descricao": "<uma frase>", "confianca": <0..1>}
Exemplo: apps de medição → "Mapa de Medição". confianca é sua confiabilidade de que
o nome representa bem o grupo. Não use nomes de pessoas."""


def infer_servicos_negocio_ia(apps: list[dict], ol: Ollama | None, min_apps: int = 3) -> list[tuple[str, str, int, list[dict], float]]:
    """Grupos por area_negocio (≥min_apps); o LLM só nomeia o grupo.

    Filtro anti-dado-sujo: descarta valores que parecem nomes de pessoas.
    Cada grupo traz a confiabilidade reportada pelo modelo (0..1)."""
    def parece_pessoa(area: str) -> bool:
        partes = area.split()
        caps = [p for p in partes if p[:1].isupper()]
        return len(partes) <= 3 and len(caps) >= 2 and area.lower() not in {
            'site portal app', 'contas setoriais', 'site portal'
        }

    grupos: dict[str, list[dict]] = defaultdict(list)
    for app in apps:
        area = (app.get('area_negocio') or '').strip()
        if area and area != '---' and not parece_pessoa(area):
            grupos[area].append(app)
    saida = []
    for area, membros in grupos.items():
        if len(membros) < min_apps:
            continue
        nome, desc, conf = f'Mapa de {area}', f'Família de {len(membros)} aplicações da área {area}', 0.5
        if ol:
            try:
                lista = '\n'.join(f"- {m['sistema']}: {(m.get('descricao') or '')[:120]}" for m in membros[:20])
                resp = ol.chat_json(SISTEMA_GRUPO, f'Área: {area}\nAplicações:\n{lista}')
                nome = (resp.get('nome') or nome).strip()[:80]
                desc = (resp.get('descricao') or desc).strip()[:300]
                conf = _confianca(resp.get('confianca'), padrao=conf)
            except OllamaError as e:
                print(f'  aviso: nome IA falhou para área {area!r}: {e}; usando "Mapa de {area}"')
        saida.append((nome, desc, len(membros), membros, conf))
    return saida

# ============================================================
# Etapa 4a: relacionamentos técnicos determinísticos
# ============================================================

def infer_relacionamentos_tecnicos(ativos: list[dict], apps: list[dict],
                                   pares_instancia: list[tuple],
                                   servicos_por_ativo: dict) -> list[tuple]:
    """Regras estruturadas (dados, não texto):

    A. mesma app em N hosts → 'Replica para' do primeiro aos demais
    B. app com banco declarado + ativo que hospeda o SGBD → 'Depende de'
    """
    ativo_por_app: dict[int, dict] = {}
    for ativo, app, *_ in pares_instancia:
        ativo_por_app.setdefault(app['id'], ativo)

    ativo_por_tipo_servico: dict[str, int] = {}
    for ativo_id, itens in servicos_por_ativo.items():
        for _, tipo, _conf in itens:
            ativo_por_tipo_servico.setdefault(tipo, ativo_id)

    rels, vistos = [], set()

    # Regra A: multi-host da mesma app → 'Replica para'
    hosts_por_app: dict[int, list[dict]] = defaultdict(list)
    for ativo, app, *_ in pares_instancia:
        hosts_por_app[app['id']].append(ativo)
    for hosts in hosts_por_app.values():
        if len(hosts) > 1:
            primario, replicas = hosts[0], hosts[1:]
            for rep in replicas:
                par = (primario['id'], rep['id'])
                if par not in vistos:
                    vistos.add(par)
                    rels.append((primario, rep, 'Replica para',
                                 f'Mesma aplicação em múltiplos hosts ({primario["nome"]} → {rep["nome"]})'))

    # Regra B: banco declarado + host do SGBD conhecido → 'Depende de'
    bancos = {
        'cassandra': ['cassandra', 'dynamodb'],
        'database': ['postgres', 'oracle', 'mysql', 'mariadb', 'sql server', 'vertica', 'totvs'],
    }
    nome_ativo = {a['id']: a['nome'] for a in ativos}
    for app in apps:
        host_ativo = ativo_por_app.get(app['id'])
        if not host_ativo:
            continue
        bds = norm(app.get('bancos_dados') or '')
        if not bds or bds in ('---', 'x'):
            continue
        for tipo_srv, palavras in bancos.items():
            if any(p in bds for p in palavras):
                db_ativo_id = ativo_por_tipo_servico.get(tipo_srv)
                if db_ativo_id and db_ativo_id != host_ativo['id']:
                    par = (host_ativo['id'], db_ativo_id)
                    if par not in vistos:
                        vistos.add(par)
                        rels.append((host_ativo, {'id': db_ativo_id, 'nome': nome_ativo[db_ativo_id]},
                                     'Depende de',
                                     f'{app["sistema"]} usa {app.get("bancos_dados")}'))
                break
    return rels

# ============================================================
# Etapa 4b: dependências citadas em texto (LLM)
# ============================================================

SISTEMA_DEP = """Dado o texto de uma aplicação e a lista de outras aplicações, identifique
de quais aplicação(ões) o texto sugere DEPENDÊNCIA (envia/recebe dados, integra, consome API).
Responda APENAS JSON: {"dependencias": [{"sistema": "<nome exato da lista>", "evidencia": "<trecho curto>", "confianca": <0..1>}]}
Regras: só inclua sistemas presentes na lista; nome EXATAMENTE igual ao da lista;
confianca é sua confiabilidade na dependência citada; se não houver dependência
clara, retorne lista vazia. Suspeita leve não conta."""


def infer_relacionamentos_ia(apps: list[dict], pares_instancia: list[tuple],
                             ol: Ollama) -> tuple[list, list]:
    """Avalia o texto de cada app contra a lista de outras; devolve
    (criáveis [origem_ativo, destino_ativo, evidência, confiança],
    potenciais sem ativo [origem, destino, evidência, confiança])."""
    ativo_por_app: dict[int, dict] = {}
    for ativo, app, *_ in pares_instancia:
        ativo_por_app.setdefault(app['id'], ativo)

    nomes = [app['sistema'] for app in apps]
    rels, pendentes, vistos = [], set(), set()
    for app in apps:
        origem_ativo = ativo_por_app.get(app['id'])
        texto = f"{app.get('objetivo') or ''} {app.get('descricao') or ''}".strip()
        if not texto or len(texto) < 30:
            continue
        lista = '\n'.join(f'- {n}' for n in nomes if n != app['sistema'])
        if not lista:
            continue
        prompt = (f'Aplicação em análise: {app["sistema"]}\n'
                  f'Texto: {texto[:600]}\n\nOutras aplicações:\n{lista}')
        try:
            resp = ol.chat_json(SISTEMA_DEP, prompt)
        except OllamaError as e:
            print(f'  aviso: dependências de {app["sistema"]!r} falharam: {e}')
            continue
        for dep in resp.get('dependencias', []) or []:
            alvo = next((a2 for a2 in apps if a2['sistema'] == dep.get('sistema')), None)
            if not alvo or alvo['id'] == app['id']:
                continue
            evidencia = (dep.get('evidencia') or '').strip()[:60]
            conf = _confianca(dep.get('confianca'))
            destino_ativo = ativo_por_app.get(alvo['id'])
            if not origem_ativo or not destino_ativo:
                pendentes.add((app['sistema'], alvo['sistema'], evidencia, conf))
                continue
            par = (origem_ativo['id'], destino_ativo['id'])
            if par not in vistos:
                vistos.add(par)
                rels.append((origem_ativo, destino_ativo, evidencia or 'dependência citada', conf))
    return rels, sorted(pendentes)

# ============================================================
# Escrita idempotente (reaproveita lógica do infer_infra_map.py)
# ============================================================

def get_or_create(api: Api, path: str, exists_key: str, exists_val: str, payload: dict, dry: bool):
    for item in api_get_all(api, path, paginated=False):
        if norm(str(item.get(exists_key, ''))) == norm(exists_val):
            return item, False
    if dry:
        return None, True
    return api.post(path, payload), True


# ============================================================
# Reconciliação de ações de baixa confiabilidade (4-olhos)
# ============================================================

def reportar_reconciliacao(api: Api,
                           acoes: list[tuple[str, str, int | None, str | None,
                                            str, str | None, float]],
                           limiar: float, dry: bool, verbose: bool) -> None:
    """Abre uma tarefa de reconciliação (fonte 'ia') com as ações inferidas.

    Ações com confiabilidade < limiar (padrão 0.9) viram itens pendentes de
    verificação manual por 2+ analistas no painel de Reconciliações; as de
    confiança suficiente são registradas já ratificadas (trilha de auditoria)."""
    if not acoes:
        if verbose:
            print('  nenhuma ação inferida para reportar à reconciliação')
        return
    baixas = [a for a in acoes if a[6] < limiar]
    if not baixas:
        print(f'  reconciliação: {len(acoes)} ação(ões) com confiança >= {limiar:.0%} '
              f'— nenhuma verificação manual necessária')
        if verbose:
            for acao, entidade, _, _, valor, _, conf in sorted(acoes, key=lambda x: x[6]):
                print(f'    conf {conf:.0%}: {acao} {entidade} {valor}')
        return
    payload = {'nome': f'Inferência IA — {len(baixas)} ação(ões) de baixa confiabilidade',
               'limiar': limiar,
               'itens': [{'acao': acao, 'entidade': entidade, 'entidade_id': eid,
                          'campo': campo, 'valor_proposto': valor, 'valor_cmdb': vcmdb,
                          'confianca': round(conf, 4)}
                         for acao, entidade, eid, campo, valor, vcmdb, conf in acoes]}
    if dry:
        print(f'  [dry-run] reconciliação: {len(baixas)} ação(ões) abaixo de {limiar:.0%} '
              f'seriam reportadas (POST /reconciliacoes/inferencia)')
        for it in payload['itens']:
            print(f'    conf {it["confianca"]:.0%}: {it["acao"]} {it["entidade"]} '
                  f'{it["valor_proposto"]}')
        return
    try:
        resp = api.post('/reconciliacoes/inferencia', payload)
    except error.HTTPError as e:
        print(f'  aviso: falha ao reportar reconciliação de inferência '
              f'(HTTP {e.code}): {e.read().decode(errors="replace")[:200]}')
        return
    rec = resp.get('reconciliacao', {})
    print(f'  reconciliação #{rec.get("id")} aberta: {resp.get("pendentes_abertos")} '
          f'item(ns) de baixa confiança (< {limiar:.0%}) aguardando 2+ analistas; '
          f'{resp.get("auto_ratificados")} auto-ratificados na trilha de auditoria')

# ============================================================
# Pipeline
# ============================================================

def run(api: Api, ol: Ollama | None, dry: bool, verbose: bool, top_k: int, limiar: float,
        lote_servicos: int, limiar_confianca: float) -> None:
    log = print
    t0 = time.time()
    ativos = api_get_all(api, '/ativos/')
    apps = api_get_all(api, '/aplicacoes/', paginated=False)
    # Ações inferidas para auditoria/reconciliação:
    # (acao, entidade, entidade_id, campo, valor_proposto, valor_cmdb, confianca)
    acoes_inferidas: list[tuple[str, str, int | None, str | None, str, str | None, float]] = []

    log(f'Fontes: {len(ativos)} ativos, {len(apps)} aplicações')
    if dry:
        log('*** DRY-RUN: nada será gravado ***')

    if ol:
        ok, detalhe = ol.tem_modelos()
        if not ok:
            log(f'aviso: {detalhe}; seguindo apenas com regras determinísticas')
            ol = None

    # --- 1. Serviços ---
    servicos_por_ativo: dict[int, list[tuple[str, str, float]]] = {}
    if ol:
        try:
            servicos_por_ativo = infer_servicos_ia(ativos, ol, lote_servicos, verbose)
        except OllamaError as e:
            log(f'aviso: etapa de serviços via IA falhou ({e}); etapa pulada')
    total_serv = sum(len(v) for v in servicos_por_ativo.values())
    log(f'\n[1] Serviços inferidos por IA: {total_serv} em {len(servicos_por_ativo)} ativos '
        f'({time.time() - t0:.0f}s)')
    existentes_srv = api_get_all(api, '/servicos/', paginated=False)
    ativos_com_srv = {s.get('ativo_id') for s in existentes_srv if s.get('ativo_id')}
    nomes_srv = {norm(s.get('nome', '')) for s in existentes_srv}
    for ativo in sorted(ativos, key=lambda x: x['id']):
        if ativo['id'] in ativos_com_srv:
            continue
        for nome, tipo, conf in servicos_por_ativo.get(ativo['id'], []):
            _, criado = get_or_create(api, '/servicos/', 'nome', nome,
                                      {'nome': nome, 'tipo': tipo, 'ativo_id': ativo['id']}, dry)
            if criado:
                acoes_inferidas.append(('criar_servico', 'servico', None, 'nome', nome,
                                        f'ativo_id={ativo["id"]}', conf))
            if verbose:
                log(f'  {"criado" if criado else "já existe"}: {nome} ({tipo}, conf {conf:.0%}) @ {ativo["nome"]}')
            break

    # --- 2. Instâncias ---
    pares: list[tuple[dict, dict, str]] = []
    if ol and apps:
        t1 = time.time()
        try:
            pares = infer_instancias_ia(ativos, apps, servicos_por_ativo, ol, top_k, limiar, verbose)
        except OllamaError as e:
            log(f'aviso: etapa de instâncias via IA falhou ({e}); etapa pulada')
        log(f'\n[2] Instâncias validadas por IA: {len(pares)} ({time.time() - t1:.0f}s)')
    else:
        log('\n[2] Instâncias via IA: pulada (sem IA ou sem aplicações)')
    existentes_inst = api_get_all(api, '/instancias-aplicacao/')
    ocupados = {i.get('ativo_id') for i in existentes_inst if i.get('ativo_id')}
    inst_por_app = {i.get('aplicacao_id') for i in existentes_inst}
    multi: dict[int, set] = defaultdict(set)
    for ativo, app, *_ in pares:
        multi[app['id']].add(ativo['id'])
    for ativo, app, motivo, conf in pares:
        if ativo['id'] in ocupados:
            if verbose:
                log(f'  conflito unique(ativo_id): {app["sistema"]} @ {ativo["nome"]} ignorado')
            continue
        if app['id'] in inst_por_app and len(multi[app['id']]) <= 1:
            if verbose:
                log(f'  app já instanciada: {app["sistema"]} ignorado')
            continue
        ocupados.add(ativo['id'])
        inst_por_app.add(app['id'])
        if not dry:
            api.post('/instancias-aplicacao/', {'aplicacao_id': app['id'], 'ativo_id': ativo['id']})
        acoes_inferidas.append(('criar_instancia', 'instancias_aplicacao', None, 'ativo_id',
                                f'{app["sistema"]} @ {ativo["nome"]}', None, conf))
        log(f'  {"[dry-run] " if dry else ""}instancia: {app["sistema"]} @ {ativo["nome"]} '
            f'(por: {motivo}, conf {conf:.0%})')

    # --- 3. Serviços de negócio ---
    t2 = time.time()
    grupos = infer_servicos_negocio_ia(apps, ol)
    log(f'\n[3] Serviços de negócio por IA: {len(grupos)} ({time.time() - t2:.0f}s)')
    for nome, desc, total, membros, conf in grupos:
        _, criado = get_or_create(api, '/servicos-negocio/', 'nome', nome,
                                  {'nome': nome, 'descricao': desc}, dry)
        if criado:
            acoes_inferidas.append(('criar_servico_negocio', 'servico_negocio', None, 'nome',
                                    nome, None, conf))
        if verbose:
            exemplos = ', '.join(m['sistema'] for m in membros[:4])
            log(f'  {"criado" if criado else "já existe"}: {nome} ← {total} apps '
                f'(ex.: {exemplos}, conf {conf:.0%})')

    # --- 4. Relacionamentos ---
    t3 = time.time()
    tipo_por_nome = {}
    for t in api_get_all(api, '/tipos-relacionamento/', paginated=False):
        tipo_por_nome[norm(t['nome'])] = t

    def tipo_id(nome: str):
        t = tipo_por_nome.get(norm(nome))
        if t:
            return t['id']
        t, _ = get_or_create(api, '/tipos-relacionamento/', 'nome', nome,
                             {'nome': nome, 'descricao': f'Tipo {nome} (inferido)'}, dry)
        if isinstance(t, tuple):  # POST devolve (status, body) no Api._req
            t = t[1]
        if t:
            tipo_por_nome[norm(nome)] = t
        return t['id'] if t else None

    existentes_rel = api_get_all(api, '/relacionamentos/', paginated=False)
    pares_rel = {(r.get('origem_id'), r.get('destino_id'), r.get('tipo_id')) for r in existentes_rel}

    def grava_rel(origem: dict, destino: dict, tipo_nome: str, motivo: str, prefixo: str,
                  confianca: float) -> bool:
        tid = tipo_id(tipo_nome)
        if not tid:
            return False
        par = (origem['id'], destino['id'], tid)
        if par in pares_rel:
            return False
        pares_rel.add(par)
        if not dry:
            api.post('/relacionamentos/', {'origem_id': origem['id'], 'destino_id': destino['id'],
                                           'tipo_id': tid,
                                           'descricao': f'{prefixo}: {motivo}'})
        acoes_inferidas.append(('criar_relacionamento', 'relacionamento', None, 'tipo',
                                f'{origem["nome"]} → {destino["nome"]} [{tipo_nome}]', None, confianca))
        log(f'  {"[dry-run] " if dry else ""}relacionamento: {origem["nome"]} → {destino["nome"]} '
            f'[{tipo_nome}] ({motivo}, conf {confianca:.0%})')
        return True

    # 4a. regras técnicas estruturadas (sempre rodam, IA ou não)
    rels_tec = infer_relacionamentos_tecnicos(ativos, apps, pares, servicos_por_ativo)
    log(f'\n[4] Relacionamentos técnicos: {len(rels_tec)} '
        f'({time.time() - t3:.0f}s)')
    for origem, destino, tipo_nome, motivo in rels_tec:
        grava_rel(origem, destino, tipo_nome, motivo, 'Inferido', 1.0)

    # 4b. dependências citadas em texto (IA)
    if ol:
        t4 = time.time()
        rels_texto, pendentes = infer_relacionamentos_ia(apps, pares, ol)
        log(f'\n[4b] Dependências citadas em texto (IA): {len(rels_texto)} criáveis, '
            f'{len(pendentes)} potenciais ({time.time() - t4:.0f}s)')
        for origem, destino, motivo, conf in rels_texto:
            grava_rel(origem, destino, 'Depende de', motivo, 'Inferido por IA de documentação', conf)
        for de, para, motivo, conf in pendentes:
            log(f'    potencial (sem ativo): {de} → {para} ({motivo}, conf {conf:.0%})')
            acoes_inferidas.append(('dependencia_potencial', 'aplicacao', None, 'dependencia',
                                    f'{de} → {para}', None, conf))

    # --- Reconciliação das ações de baixa confiabilidade (4-olhos) ---
    reportar_reconciliacao(api, acoes_inferidas, limiar_confianca, dry, verbose)

    log(f'\n=== Concluído em {time.time() - t0:.0f}s {"(dry-run — nada gravado)" if dry else ""} ===')


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('--api', default='http://localhost:8000')
    ap.add_argument('--token', required=True)
    ap.add_argument('--dry-run', action='store_true')
    ap.add_argument('--verbose', action='store_true')
    ap.add_argument('--ollama', default='http://localhost:11434')
    ap.add_argument('--chat-model', default='llama3.2')
    ap.add_argument('--embed-model', default='nomic-embed-text')
    ap.add_argument('--top-k', type=int, default=5)
    ap.add_argument('--limiar', type=float, default=0.35)
    ap.add_argument('--lote-servicos', type=int, default=40)
    ap.add_argument('--limiar-confianca', type=float, default=0.9,
                    help='confiança mínima (0..1) para a ação inferida dispensar '
                         'verificação manual; abaixo disso abre item de reconciliação')
    ap.add_argument('--sem-ia', action='store_true',
                    help='desliga as etapas de LLM (só regras determinísticas)')
    args = ap.parse_args()

    api = Api(args.api, args.token)
    ol = None if args.sem_ia else Ollama(args.ollama, args.chat_model, args.embed_model)
    try:
        run(api, ol, args.dry_run, args.verbose, args.top_k, args.limiar,
            args.lote_servicos, args.limiar_confianca)
    except error.HTTPError as e:
        corpo = e.read().decode(errors='replace')[:300]
        print(f'ERRO HTTP {e.code} em {e.url}: {corpo}', file=sys.stderr)
        sys.exit(1)


if __name__ == '__main__':
    main()