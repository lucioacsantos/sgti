"""Importa dados de exemplo de um dump pgAdmin (INSERTs) para o banco do SGTI CMDB.

Origem esperada: diretório com arquivos *_*.sql exportados do pgAdmin
(ex.: /home/lucio/Downloads/cmdb_banco_teste/).

O que importa:
  - aplicacao        → todos os sistemas (get_or_create por 'sistema')
  - ativo            → 16 servidores com mapeamento de FKs de referência
  - endereco_ip      → IPs mapeados por posição aos ativos importados
  - referências      → criticidade, tipo_ativo, status_ativo, ambiente, areas, sor

O que ignora:
  - service_accounts (tokens obsoletos/conta de teste — risco de segurança)
  - alembic_version
  - tabelas vazias no dump (cluster, namespace, relacionamentos, serviços...)

Uso:
  cd backend && ../venv/bin/python import_test_data.py <diretorio> [--dry-run]

Idempotente: reexecuções não duplicam registros.
"""
import datetime
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import models
from database import SessionLocal, engine

models.Base.metadata.create_all(bind=engine)


# ===== Parser do dump pgAdmin =====

def split_statements(text: str):
    stmts, buf, in_str, i = [], [], False, 0
    while i < len(text):
        ch = text[i]
        if in_str:
            if ch == "'":
                if text[i + 1:i + 2] == "'":
                    buf.append("''")
                    i += 2
                    continue
                in_str = False
            buf.append(ch)
            i += 1
            continue
        if ch == "'":
            in_str = True
            buf.append(ch)
            i += 1
            continue
        if ch == ';':
            stmts.append(''.join(buf))
            buf = []
            i += 1
            continue
        buf.append(ch)
        i += 1
    tail = ''.join(buf)
    if tail.strip():
        stmts.append(tail)
    return stmts


def parse_insert(stmt: str):
    """Retorna (tabela, [colunas], [[valores], ...]) ou None."""
    header_end = stmt.find(' VALUES')
    if header_end < 0:
        return None
    header = stmt[:header_end].strip()
    if not header.upper().startswith('INSERT INTO'):
        return None
    rest = header[len('INSERT INTO'):].strip()
    paren = rest.index('(')
    table = rest[:paren].strip().strip('"')
    cols = [c.strip().strip('"') for c in rest[paren + 1:rest.rindex(')')].split(',')]
    body = stmt[header_end + len(' VALUES'):]

    tuples, cur, depth, in_str, i = [], [], 0, False, 0
    while i < len(body):
        ch = body[i]
        if in_str:
            if ch == "'":
                if body[i + 1:i + 2] == "'":
                    cur.append("''")
                    i += 2
                    continue
                in_str = False
            cur.append(ch)
            i += 1
            continue
        if ch == "'":
            in_str = True
            cur.append(ch)
            i += 1
            continue
        if ch == '(':
            depth += 1
            if depth == 1:
                cur = []
                i += 1
                continue
        if ch == ')':
            depth -= 1
            if depth == 0:
                tuples.append(cur)
                cur = []
                i += 1
                continue
        if depth >= 1:
            cur.append(ch)
        i += 1

    rows = [[_convert(v) for v in _split_values(''.join(t))] for t in tuples]
    return table.split('.')[-1], cols, rows


def _split_values(s: str):
    vals, cur, in_str, i = [], [], False, 0
    while i < len(s):
        ch = s[i]
        if in_str:
            if ch == "'":
                if s[i + 1:i + 2] == "'":
                    cur.append("'")
                    i += 2
                    continue
                in_str = False
                i += 1
                continue
            cur.append(ch)
            i += 1
            continue
        if ch == "'":
            in_str = True
            i += 1
            continue
        if ch == ',':
            vals.append(''.join(cur).strip())
            cur = []
            i += 1
            continue
        cur.append(ch)
        i += 1
    vals.append(''.join(cur).strip())
    return vals


def _convert(raw: str):
    if raw == 'NULL':
        return None
    if raw == 'true':
        return True
    if raw == 'false':
        return False
    if raw.startswith("'") and raw.endswith("'"):
        return raw[1:-1].replace("''", "'")
    try:
        return int(raw)
    except ValueError:
        pass
    try:
        return float(raw)
    except ValueError:
        return raw


def _parse_dt(value):
    if value is None:
        return None
    if isinstance(value, datetime.datetime):
        return value
    for fmt in ('%Y-%m-%d %H:%M:%S.%f', '%Y-%m-%d %H:%M:%S', '%Y-%m-%d'):
        try:
            return datetime.datetime.strptime(str(value), fmt)
        except ValueError:
            continue
    return None


# ===== Importação =====

def get_or_create(db, model, defaults=None, **kwargs):
    obj = db.query(model).filter_by(**kwargs).first()
    if obj:
        return obj, False
    obj = model(**kwargs, **(defaults or {}))
    db.add(obj)
    db.flush()
    return obj, True


def import_dir(db, directory: str, dry_run: bool):
    files = sorted(f for f in os.listdir(directory) if f.endswith('.sql'))
    stats = {}
    warnings = []

    # Estado de referência do dump: ids posicionais (1-based) por tabela
    ref = {'tipo_ativo': {}, 'criticidade': {}, 'status_ativo': {},
           'ambiente': {}, 'sor': {}, 'areas': {}}
    ativos_importados = []  # ordem de inserção == ids originais 17..32

    def bump(table, created):
        c, u = stats.get(table, (0, 0))
        stats[table] = (c + (1 if created else 0), u + (0 if created else 1))

    # Passo 1 — referências e aplicações
    for fname in files:
        stmts = split_statements(open(os.path.join(directory, fname), encoding='utf-8').read())
        for stmt in stmts:
            parsed = parse_insert(stmt)
            if not parsed:
                continue
            table, cols, rows = parsed
            if table not in ref and table not in ('aplicacao',):
                continue
            for row in rows:
                rec = dict(zip(cols, row))
                if table == 'criticidade':
                    obj, created = get_or_create(db, models.Criticidade, nivel=rec['nivel'])
                    ref['criticidade'][len(ref['criticidade']) + 1] = obj
                elif table == 'tipo_ativo':
                    obj, created = get_or_create(db, models.TipoAtivo, nome=rec['nome'])
                    ref['tipo_ativo'][len(ref['tipo_ativo']) + 1] = obj
                elif table == 'status_ativo':
                    obj, created = get_or_create(db, models.StatusAtivo, nome=rec['nome'])
                    ref['status_ativo'][len(ref['status_ativo']) + 1] = obj
                elif table == 'ambiente':
                    obj, created = get_or_create(db, models.Ambiente, nome=rec['nome'])
                    ref['ambiente'][len(ref['ambiente']) + 1] = obj
                elif table == 'sor':
                    obj, created = get_or_create(
                        db, models.SistemaOperacional,
                        defaults={'descricao': rec['descricao'], 'lifecycle': rec.get('lifecycle') or None},
                        abreviacao=rec['abreviacao'])
                    ref['sor'][len(ref['sor']) + 1] = obj
                elif table == 'areas':
                    obj, created = get_or_create(
                        db, models.Areas, nome=rec['nome'], defaults={'sigla': rec.get('sigla') or rec['nome']})
                    ref['areas'][len(ref['areas']) + 1] = obj
                elif table == 'aplicacao':
                    _, created = get_or_create(
                        db, models.Aplicacao,
                        defaults={
                            'descricao': rec.get('descricao'),
                            'objetivo': rec.get('objetivo'),
                            'linguagens': rec.get('linguagens'),
                            'bancos_dados': rec.get('bancos_dados'),
                            'area_tecnologia': rec.get('area_tecnologia'),
                            'area_negocio': rec.get('area_negocio'),
                            'created_at': _parse_dt(rec.get('created_at')),
                        },
                        sistema=rec['sistema'])
                else:
                    continue
                bump(table, created)

    # Fallback: dump referencia tipo_id=3 inexistente (só há VxRail=1, VM=2)
    tipo_fallback, created = get_or_create(db, models.TipoAtivo, nome='Servidor Virtual')
    if created:
        warnings.append("tipo_ativo id=3 referenciado pelos ativos não existe no dump — mapeado para 'Servidor Virtual'")
    ref['tipo_ativo'].setdefault(3, tipo_fallback)

    # Passo 2 — ativos
    for fname in files:
        stmts = split_statements(open(os.path.join(directory, fname), encoding='utf-8').read())
        for stmt in stmts:
            parsed = parse_insert(stmt)
            if not parsed or parsed[0] != 'ativo':
                continue
            _, cols, rows = parsed
            for row in rows:
                rec = dict(zip(cols, row))
                if db.query(models.Ativo).filter_by(nome=rec['nome']).first():
                    bump('ativo', False)
                    continue
                obj = models.Ativo(
                    nome=rec['nome'],
                    descricao=rec.get('descricao'),
                    tipo_id=ref['tipo_ativo'][rec['tipo_id']].id,
                    ambiente_id=ref['ambiente'][rec['ambiente_id']].id,
                    status_id=ref['status_ativo'][rec['status_id']].id,
                    criticidade_id=ref['criticidade'][rec['criticidade_id']].id,
                    sor_id=ref['sor'][rec['sor_id']].id if rec.get('sor_id') else None,
                    areas_id=ref['areas'][rec['areas_id']].id if rec.get('areas_id') else None,
                    created_at=_parse_dt(rec.get('created_at')),
                    updated_at=_parse_dt(rec.get('updated_at')),
                )
                db.add(obj)
                db.flush()
                ativos_importados.append(obj)
                bump('ativo', True)

    # Passo 3 — endereços IP (dump usa ids originais 17..32 == posição dos ativos importados)
    ip_offset = 17
    for fname in files:
        stmts = split_statements(open(os.path.join(directory, fname), encoding='utf-8').read())
        for stmt in stmts:
            parsed = parse_insert(stmt)
            if not parsed or parsed[0] != 'endereco_ip':
                continue
            _, cols, rows = parsed
            for row in rows:
                rec = dict(zip(cols, row))
                idx = rec['ativo_id'] - ip_offset
                if idx < 0 or idx >= len(ativos_importados):
                    warnings.append(f"IP {rec['ip']} ignorado: ativo_id={rec['ativo_id']} sem correspondente")
                    bump('endereco_ip', False)
                    continue
                alvo = ativos_importados[idx]
                _, created = get_or_create(
                    db, models.EnderecoIp,
                    defaults={
                        'tipo': rec.get('tipo') or 'IPv4',
                        'interface': rec.get('interface'),
                        'descricao': rec.get('descricao'),
                        'primario': bool(rec.get('primario')),
                        'ativo': bool(rec.get('ativo', True)),
                        'created_at': _parse_dt(rec.get('created_at')),
                        'updated_at': _parse_dt(rec.get('updated_at')),
                    },
                    ativo_id=alvo.id, ip=rec['ip'])
                bump('endereco_ip', created)

    if dry_run:
        db.rollback()
    else:
        db.commit()
    return stats, warnings


def main():
    args = [a for a in sys.argv[1:] if not a.startswith('--')]
    dry_run = '--dry-run' in sys.argv
    if not args or not os.path.isdir(args[0]):
        print(__doc__)
        sys.exit(1)

    from database import SessionLocal
    db = SessionLocal()
    try:
        stats, warnings = import_dir(db, args[0].rstrip('/'), dry_run)
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()

    modo = 'DRY-RUN (nada gravado)' if dry_run else 'IMPORTADO'
    print(f'=== Importação {modo}: {args[0]} ===')
    for table, (criados, existentes) in sorted(stats.items()):
        print(f'  {table:<14} {criados:>4} importados | {existentes:>4} já existentes')
    if warnings:
        print('--- Avisos ---')
        for w in warnings:
            print(f'  ⚠ {w}')


if __name__ == '__main__':
    main()