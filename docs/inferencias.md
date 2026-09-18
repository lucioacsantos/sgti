# Importação e inferência do mapa de TI

Dois scripts de suporte preenchem o CMDB a partir de dados existentes. Ambos são **idempotentes** (reexecução não duplica) e operam **exclusivamente via API** (service token) ou por endpoints idempotentes — nunca gravam direto no banco fora dos upserts oficiais.

Pré-requisito: service token ativo (criado em Administração → Tokens de Serviço ou pelo seed).

---

## 1. import_test_data.py — importar dump de ativos/aplicações

Importa um diretório com arquivos de INSERTs exportados do pgAdmin (`*.sql`), ex.:

```bash
cd backend
set -a; source .env; set +a
../venv/bin/python import_test_data.py /caminho/dump/ --dry-run   # simula
../venv/bin/python import_test_data.py /caminho/dump/             # grava
```

### O que importa

| Tabela do dump | Destino | Estratégia |
|---|---|---|
| `ativo` | ativos | get-or-create por `nome` |
| `aplicacao` | aplicações | get-or-create por `sistema` |
| `endereco_ip` | IPs | mapeados por posição ao ativo importado (o dump referencia ids originais) |
| `criticidade`, `tipo_ativo`, `status_ativo`, `ambiente`, `sor`, `areas` | dados mestre | get-or-create |

### O que ignora de propósito

- `service_accounts` (tokens bcrypt obsoletos + contas de teste — risco de segurança)
- `alembic_version` e tabelas vazias

### Particularidades tratadas

- FKs inexistentes no dump (ex.: `tipo_id=3` apontando para tipo ausente) recebem mapeamento com aviso no output
- IPs do dump ligados por **ordem de inserção** aos ativos importados
- Modo `--dry-run` faz rollback — nada é gravado

---

## 2. infer_infra_map.py — gerar o mapa por inferência

```bash
../venv/bin/python infer_infra_map.py \
    --api http://localhost:8000 \
    --token <service-token> \
    [--dry-run] [--verbose]
```

Tudo **via API REST** (não acessa o banco diretamente). Estratégias executadas em sequência:

### [1] Serviços a partir de descrições de ativos (lexical)

Dicionário de padrões regex → (nome do serviço, tipo), ordenado do mais específico ao mais genérico:

```
ERP PROTHEUS DBACCESS  → Protheus DBAccess (database)
ERP PROTHEUS APPSERVER → Protheus AppServer (appserver)
Cassandra              → Cassandra (database)
Apache AirFlow         → Apache Airflow (scheduler)
Apache Nifi / Nifi     → Apache NiFi (integration)
DATA POWER / APP Connect / Broker ... / LDAP / Bastion / Database Dev ...
```

- Normaliza acentos/caixa e casa em `nome + descricao` do ativo
- **1 serviço por ativo** (o `UNIQUE(ativo_id)` do schema) — fica o match mais específico
- Criação idempotente: `GET /servicos/` compara por nome antes do `POST`

### [2] Instâncias de aplicação (match ativo ↔ app)

Cada lado é reduzido a um conjunto de tokens (palavras normalizadas, sem stopwords como "sistema", "servidor", "portal"):

- Ativo: nome + descrição + nomes dos serviços já inferidos
- Aplicação: sistema + descrição + objetivo

**Casamento** (`infer_instancias`): par ativo×aplicação é candidato quando

- ≥2 tokens compartilhados, **ou**
- ≥1 token **forte** no nome do sistema (`protheus`, `cassandra`, `airflow`, `nifi`, `ckan`, `ldap`, `atlas`) — evita casamentos por texto livre como "Power BI" ↔ "DATA**POWER**"

**Escrita**: respeita `UNIQUE(ativo_id)` e não instancia a mesma aplicação duas vezes — exceto quando a aplicação casa com **múltiplos ativos** (ex.: Protheus em dxer01/02/03 → 3 instâncias). A porta/path ficam nulos para a automação real preencher depois.

### [3] Serviços de negócio por área

Agrupa aplicações por `area_negocio`; grupos com ≥3 apps viram um serviço de negócio ("Mapa de <área>"). Um filtro anti-dado-sujo descarta valores que parecem **nomes de pessoas** (comuns nesse campo: "Daniele Batista" etc.).

### [4] Relacionamentos — regras técnicas (dados estruturados)

Prioridade para evidência estruturada, não texto:

- **Regra A — multi-host**: mesma aplicação em N ativos → `Replica para` do primeiro para os demais (Protheus: dxer01 → dxer02, dxer01 → dxer03)
- **Regra B — banco de dados**: aplicação com `bancos_dados` declarado (Oracle, PostgreSQL, TOTVS...) + ativo que hospeda o SGBD correspondente (pelos serviços inferidos) → `Depende de` (app host → db host)

O tipo de relacionamento é resolvido da lista de tipos (cria se faltar).

### [4b] Relacionamentos — dependências citadas em documentação

Padrões explícitos no `objetivo`/`descricao` das aplicações ("envio de dados ... para ABM", "portal de dados abertos", "gerenciadas pelo BPM") → `Depende de` entre os ativos das duas aplicações. Se qualquer lado não tem ativo associado, o par é listado como **potencial** (não gravado) — evidência para cadastro futuro.

---

## Segurança e determinismo

- **Somente criação idempotente** — nunca muta nem apaga registros existentes; automações reais (Zabbix etc.) refinam/substituem depois pelos mesmos endpoints
- `--dry-run` em ambos os scripts para revisão antes de gravar
- Todo POST passa pela autenticação da API (service token) e os endpoints oficiais gravam audit log
- Resultado detalhado no output: o que criou, o que já existia e os potenciais descartados

## Ordem recomendada de execução

```bash
seed.py                          # dados mestre
import_test_data.py <dump>/      # ativos + aplicações reais (opcional)
# tipos de relacionamento (uma vez):
#   POST /tipos-relacionamento/ para cada tipo
infer_infra_map.py --token ...   # serviços, instâncias, relacionamentos
```

Reexecutar qualquer script é seguro — só "já existe" no output.