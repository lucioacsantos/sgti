"""Inferência de mapa de TI a partir de ativos e aplicações existentes.

Usa SEMPRE a API do backend (nunca acesso direto ao banco) autenticada com
service token (automações). Idempotente: reexecuções não duplicam registros.

Estratégias (conforme análise do cenário):
  1. Parsing lexical de ativo.descricao       → servico (nome/tipo)
  2. Match ativo ↔ aplicação (tokens)          → instancia_aplicacao
  3. Agrupamento de apps por area_negocio      → servico_negocio
  4. Dependências citadas em texto livre       → tipo_relacionamento + relacionamento

Uso:
  cd backend && ../venv/bin/python infer_infra_map.py --api http://localhost:8000 \
      --token <service-token> [--dry-run] [--verbose]
"""
import argparse
import json
import re
import sys
import unicodedata
from collections import defaultdict
from urllib import error, parse, request

# ============================================================
# Dicionário lexical: padrão → (nome serviço, tipo serviço)
# Ordem importa (mais específico primeiro).
# ============================================================
SERVICO_PADROES: list[tuple[str, str, str]] = [
    (r'ERP\s+PROTHEUS\s+DBACCESS', 'Protheus DBAccess', 'database'),
    (r'ERP\s+PROTHEUS\s+APPSERVER', 'Protheus AppServer', 'appserver'),
    (r'ERP\s+PROTHEUS', 'Protheus', 'erp'),
    (r'Cassandra', 'Cassandra', 'database'),
    (r'Apache\s+AirFlow', 'Apache Airflow', 'scheduler'),
    (r'Apache\s+Nifi', 'Apache NiFi', 'integration'),
    (r'\bNifi\b', 'Apache NiFi', 'integration'),
    (r'Apache\s+Atlas', 'Apache Atlas', 'metadata'),
    (r'\bCKAN\b', 'CKAN', 'data-portal'),
    (r'DATA\s*POWER', 'IBM DataPower', 'gateway'),
    (r'APP\s+Connect', 'IBM App Connect', 'integration'),
    (r'BROKER\s+PLAT\s+INTEGRACAO', 'Broker Plataforma de Integração', 'integration'),
    (r'\bLDAP\b', 'LDAP', 'directory'),
    (r'\bBastion\b', 'Bastion SSH', 'security'),
    (r'Database\s+Dev', 'Banco de Dados', 'database'),
]

# Tokens genéricos ignorados no match ativo ↔ aplicação
TOKENS_APP_IGNORE = {
    'sistema', 'servidor', 'apache', 'ambiente', 'plataforma',
    'gestao', 'portal', 'dados', 'processo', 'app', 'software',
    'servico', 'gerenciamento', 'utilizado', 'database', 'desenvolvimento',
    'futuro', 'standalone', 'integracao', 'power', 'automate', 'copilot',
}

# Tokens "fortes" para match ativo ↔ aplicação (≥1 já basta quando presente
# no nome do sistema): nomes proprietários inequívocos
TOKENS_FORTES = {
    'protheus', 'cassandra', 'airflow', 'nifi', 'ckan', 'ldap', 'atlas',
}


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


def norm(txt: str) -> str:
    txt = unicodedata.normalize('NFD', (txt or '').lower())
    return ''.join(c for c in txt if unicodedata.category(c) != 'Mn')


def tokens(txt: str) -> set[str]:
    words = re.findall(r'[a-z0-9]{3,}', norm(txt))
    return {w for w in words if w not in TOKENS_APP_IGNORE}


def api_get_all(api: Api, path: str, params: dict | None = None, paginated: bool = True) -> list:
    """GET completo. Se paginated=False (endpoint ignora skip/limit), uma única chamada."""
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


def infer_servicos(ativos: list[dict]) -> dict[int, list[tuple[str, str]]]:
    """Estratégia 1: descrição do ativo → serviços (nome, tipo).

    O schema impõe UNIQUE(ativo_id) em servico — 1 serviço por ativo.
    Mantém apenas o match mais específico (primeiro do dicionário ordenado)."""
    resultado = {}
    for a in ativos:
        desc = norm(f"{a.get('nome', '')} {a.get('descricao') or ''}")
        for padrao, nome, tipo in SERVICO_PADROES:
            if re.search(padrao, desc, re.I):
                resultado[a['id']] = [(nome, tipo)]
                break
    return resultado


def infer_instancias(ativos: list[dict], apps: list[dict],
                     servicos_por_ativo: dict) -> list[tuple[dict, dict, str]]:
    """Estratégia 2: match ativo ↔ aplicação por tokens compartilhados (≥2)."""
    tokens_ativos = {}
    for a in ativos:
        base = tokens(f"{a['nome']} {a.get('descricao') or ''}")
        for nome, _ in servicos_por_ativo.get(a['id'], []):
            base |= tokens(nome)
        tokens_ativos[a['id']] = base

    pares = []
    for app in apps:
        t_sistema = tokens(app.get('sistema', ''))
        t_app = t_sistema | tokens(app.get('descricao') or '') | tokens(app.get('objetivo') or '')
        if not t_app:
            continue
        for a in ativos:
            inter = tokens_ativos[a['id']] & t_app
            forte = inter & TOKENS_FORTES
            # token forte só conta se aparecer no NOME do sistema (evita 'Atlasgov' ↔ Apache Atlas)
            forte_valido = forte & t_sistema
            if len(inter) >= 2 or forte_valido:
                motivo = ', '.join(sorted(forte_valido or inter)[:4])
                pares.append((a, app, motivo))
    return pares


def infer_servicos_negocio(apps: list[dict], min_apps: int = 3) -> list[tuple[str, str, list[dict]]]:
    """Estratégia 3: agrupa apps por area_negocio; grupos grandes → serviço de negócio.

    Descarta valores que parecem nomes de pessoas (2 palavras capitalizadas ou
    contendo preposição 'de' entre capitalized), dado sujo comum nesse campo."""
    def parece_pessoa(area: str) -> bool:
        partes = area.split()
        caps = [p for p in partes if p[:1].isupper()]
        return len(partes) <= 3 and len(caps) >= 2 and area.lower() not in {
            'site portal app', 'contas setoriais', 'site portal'
        }

    grupos = defaultdict(list)
    for app in apps:
        area = (app.get('area_negocio') or '').strip()
        if area and area != '---' and not parece_pessoa(area):
            grupos[area].append(app)
    return [(area, len(m), m) for area, m in grupos.items() if len(m) >= min_apps]


def infer_relacionamentos_texto(apps: list[dict],
                                pares_instancia: list[tuple]) -> tuple[list, list]:
    """Dependências citadas em objetivo/descrição (padrões explícitos).

    Retorna (criáveis, potenciais) — criáveis exigem ativo em ambos os lados.
    """
    ativo_por_app = {}
    for ativo, app, _ in pares_instancia:
        ativo_por_app.setdefault(app['id'], ativo)

    padroes = [
        (re.compile(r'envio\s+de\s+dados\s+de\s+consulta\s+para\s+abm', re.I), 'abm'),
        (re.compile(r'portal\s+de\s+dados\s+abertos', re.I), 'pda portal'),
        (re.compile(r'gerenciadas\s+pelo\s+bpm', re.I), 'baw'),
        (re.compile(r'integra[cç][aã]o\s+com\s+outlook\s*365', re.I), 'cale'),
    ]
    sistema_por_norm = {}
    for app in apps:
        chave = norm(app['sistema'])
        if chave not in sistema_por_norm:
            sistema_por_norm[chave] = app

    rels, vistos = [], set()
    pendentes = []
    for app in apps:
        origem_ativo = ativo_por_app.get(app['id'])
        texto = norm(f"{app.get('objetivo') or ''} {app.get('descricao') or ''}")
        if not texto:
            continue
        for padrao, alvo_chave in padroes:
            m = padrao.search(texto)
            if not m:
                continue
            alvo_app = next((cand for chave, cand in sistema_por_norm.items()
                             if chave.startswith(alvo_chave)), None)
            if not alvo_app or alvo_app['id'] == app['id']:
                continue
            destino_ativo = ativo_por_app.get(alvo_app['id'])
            if not origem_ativo or not destino_ativo:
                pendentes.append((app['sistema'], alvo_app['sistema'], m.group(0)[:40]))
                continue
            par = (origem_ativo['id'], destino_ativo['id'])
            if par not in vistos:
                vistos.add(par)
                rels.append((origem_ativo, destino_ativo, m.group(0)[:40]))
            break
    return rels, pendentes


def infer_relacionamentos_tecnicos(ativos: list[dict], apps: list[dict],
                                   pares_instancia: list[tuple],
                                   servicos_por_ativo: dict) -> list[tuple]:
    """Relacionamentos técnicos determinísticos (dados estruturados, não texto).

    Regras:
      - Ativo executa serviço nele instalado → origem=ativo, destino=ativo (mesma máquina)
        Não se aplica (relacionamento liga ativos distintos) — usado para validar.
      - Instâncias da mesma aplicação em ativos distintos: primeiro ativo
        (produção/apserver) 'Replica para' os demais (ex.: Protheus dxer01 → dxer02/03).
      - Apps com mesmo SGBD citado + ativo do SGBD conhecido → 'Depende de'
        (ex.: app com PostgreSQL em dxpg01).

    Retorna (origem_ativo, destino_ativo, tipo_nome, motivo).
    """
    ativo_por_app = {}
    for ativo, app, _ in pares_instancia:
        ativo_por_app.setdefault(app['id'], ativo)

    # ativo por tipo de serviço inferido (cassandra/database etc.)
    ativo_por_tipo_servico = {}
    for ativo_id, itens in servicos_por_ativo.items():
        for nome, tipo in itens:
            ativo_por_tipo_servico.setdefault(tipo, ativo_id)

    rels, vistos = [], set()

    # Regra A: multi-host da mesma app → 'Replica para' (primeiro → demais)
    hosts_por_app = defaultdict(list)
    for ativo, app, _ in pares_instancia:
        hosts_por_app[app['id']].append(ativo)
    for app_id, hosts in hosts_por_app.items():
        if len(hosts) > 1:
            primario, replicas = hosts[0], hosts[1:]
            for rep in replicas:
                par = (primario['id'], rep['id'])
                if par not in vistos:
                    vistos.add(par)
                    rels.append((primario, rep, 'Replica para',
                                 f'Mesma aplicação em múltiplos hosts ({primario["nome"]} → {rep["nome"]})'))

    # Regra B: ativo com serviço 'database' + apps com bancos_dados compatíveis
    # que têm instância → 'Depende de' app_host → db_host
    bancos = {
        'cassandra': ['cassandra', 'dynamodb'],
        'database': ['postgres', 'oracle', 'mysql', 'mariadb', 'sql server', 'vertica', 'totvs'],
    }
    ativo_por_app = {}
    for ativo, app, _ in pares_instancia:
        ativo_por_app[app['id']] = ativo
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


def get_or_create(api: Api, path: str, exists_key: str, exists_val: str,
                  payload: dict, dry: bool):
    """Cria recurso se ainda não existir. Retorna (item|None, criado)."""
    for item in api_get_all(api, path, paginated=False):
        if norm(str(item.get(exists_key, ''))) == norm(exists_val):
            return item, False
    if dry:
        return None, True
    return api.post(path, payload), True


def run(api: Api, dry: bool, verbose: bool) -> None:
    log = print
    ativos = api_get_all(api, '/ativos/')
    apps = api_get_all(api, '/aplicacoes/', paginated=False)

    log(f'Fontes: {len(ativos)} ativos, {len(apps)} aplicações')
    if dry:
        log('*** DRY-RUN: nada será gravado ***')

    # --- Estratégia 1: servicos a partir da descrição dos ativos ---
    servicos_por_ativo = infer_servicos(ativos)
    total_serv = sum(len(v) for v in servicos_por_ativo.values())
    log(f'\n[1] Serviços inferidos de descrições: {total_serv} em {len(servicos_por_ativo)} ativos')
    for ativo in sorted(ativos, key=lambda x: x['id']):
        for nome, tipo in servicos_por_ativo.get(ativo['id'], []):
            _, criado = get_or_create(api, '/servicos/', 'nome', nome,
                                      {'nome': nome, 'tipo': tipo, 'ativo_id': ativo['id']}, dry)
            if verbose:
                acao = 'criado' if criado else 'já existe (ativo mantido)'
                log(f'  {acao}: {nome} ({tipo}) @ {ativo["nome"]}')

    # --- Estratégia 2: instâncias de aplicação ---
    pares = infer_instancias(ativos, apps, servicos_por_ativo)
    log(f'\n[2] Instâncias de aplicação inferidas: {len(pares)}')
    existentes_inst = api_get_all(api, '/instancias-aplicacao/')
    ocupados = {i.get('ativo_id') for i in existentes_inst if i.get('ativo_id')}
    inst_por_app = {i.get('aplicacao_id') for i in existentes_inst}
    # apps que casam com múltiplos ativos (ex.: Protheus em dxer01/02/03)
    # podem receber uma instância por ativo; apps single-host só a primeira
    multi = defaultdict(set)
    for ativo, app, _ in pares:
        multi[app['id']].add(ativo['id'])
    for ativo, app, motivo in pares:
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
        log(f'  {"[dry-run] " if dry else ""}instancia: {app["sistema"]} @ {ativo["nome"]} (por: {motivo})')

    # --- Estratégia 3: serviços de negócio por área ---
    grupos = infer_servicos_negocio(apps)
    log(f'\n[3] Serviços de negócio (grupos ≥3 apps por área): {len(grupos)}')
    for area, total, membros in grupos:
        nome_sn = f'Mapa de {area}'
        payload = {'nome': nome_sn,
                   'descricao': f'Família de {total} aplicações da área {area} (inferido do cadastro de aplicações)'}
        _, criado = get_or_create(api, '/servicos-negocio/', 'nome', nome_sn, payload, dry)
        if verbose:
            exemplos = ', '.join(m['sistema'] for m in membros[:4])
            log(f'  {"criado" if criado else "já existe"}: {nome_sn} ← {total} apps (ex.: {exemplos})')

    # --- Estratégia 4: tipos + relacionamentos (técnicos + textuais) ---
    tipo_por_nome = {}
    for t in api_get_all(api, '/tipos-relacionamento/', paginated=False):
        tipo_por_nome[norm(t['nome'])] = t

    def tipo_id(nome: str):
        t = tipo_por_nome.get(norm(nome))
        if t:
            return t['id']
        t, _ = get_or_create(api, '/tipos-relacionamento/', 'nome', nome,
                             {'nome': nome, 'descricao': f'Tipo {nome} (inferido)'}, dry)
        if t:
            tipo_por_nome[norm(nome)] = t
        return t['id'] if t else None

    # 4a. regras técnicas estruturadas
    rels_tec = infer_relacionamentos_tecnicos(ativos, apps, pares, servicos_por_ativo)
    log(f'\n[4] Relacionamentos técnicos inferidos: {len(rels_tec)}')
    existentes_rel = api_get_all(api, '/relacionamentos/', paginated=False)
    pares_rel = {(r.get('origem_id'), r.get('destino_id'), r.get('tipo_id')) for r in existentes_rel}
    for origem, destino, tipo_nome, motivo in rels_tec:
        tid = tipo_id(tipo_nome)
        if not tid:
            continue
        par = (origem['id'], destino['id'], tid)
        if par in pares_rel:
            if verbose:
                log(f'  já existe: {origem["nome"]} → {destino["nome"]} ({tipo_nome})')
            continue
        pares_rel.add(par)
        if not dry:
            api.post('/relacionamentos/', {'origem_id': origem['id'], 'destino_id': destino['id'],
                                           'tipo_id': tid, 'descricao': f'Inferido: {motivo}'})
        log(f'  {"[dry-run] " if dry else ""}relacionamento: {origem["nome"]} → {destino["nome"]} [{tipo_nome}] ({motivo})')

    # 4b. dependências citadas em texto (tipo 'Depende de')
    rels_texto, pendentes = infer_relacionamentos_texto(apps, pares)
    if rels_texto or pendentes:
        log(f'\n[4b] Dependências citadas em documentação: {len(rels_texto)} criáveis, {len(pendentes)} potenciais')
        for origem, destino, motivo in rels_texto:
            tid = tipo_id('Depende de')
            par = (origem['id'], destino['id'], tid)
            if par in pares_rel:
                continue
            pares_rel.add(par)
            if not dry:
                api.post('/relacionamentos/', {'origem_id': origem['id'], 'destino_id': destino['id'],
                                               'tipo_id': tid,
                                               'descricao': f'Inferido de documentação: {motivo}'})
            log(f'  {"[dry-run] " if dry else ""}relacionamento: {origem["nome"]} → {destino["nome"]} ({motivo})')
        for de, para, motivo in pendentes:
            log(f'    potencial (sem ativo): {de} → {para} ({motivo})')

    log(f'\n=== Concluído {"(dry-run — nada gravado)" if dry else ""} ===')


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('--api', default='http://localhost:8000')
    ap.add_argument('--token', required=True)
    ap.add_argument('--dry-run', action='store_true')
    ap.add_argument('--verbose', action='store_true')
    args = ap.parse_args()

    api = Api(args.api, args.token)
    try:
        run(api, args.dry_run, args.verbose)
    except error.HTTPError as e:
        corpo = e.read().decode(errors='replace')[:300]
        print(f'ERRO HTTP {e.code} em {e.url}: {corpo}', file=sys.stderr)
        sys.exit(1)


if __name__ == '__main__':
    main()