# SGTI CMDB

Sistema de Gerenciamento de TI — Configuration Management Database com backend FastAPI e frontend Vue 3.

## Arquitetura resumida

- **Backend**: FastAPI + SQLAlchemy + PostgreSQL, autenticação dupla (AD/LDAP via JWT + service tokens), 2FA TOTP, auditoria.
- **Frontend**: Vue 3 + Vite + Tailwind CSS, Pinia, vue-router.
- **Reconciliação**: detecção automática de discrepâncias (regras próprias e fonte Zabbix via webhook) com workflow de quatro olhos.
- **IA híbrida**: LLM on-premise (compatível Ollama) ou engine local em CPU para RAG e inferência assistida.
- **Documentação de funcionalidades**: veja [`docs/`](docs/README.md).
- **Referência de API**: Swagger em `http://localhost:8000/docs`.

---

## Instalação

### Pré-requisitos

- Python 3.12+
- Node.js 18+
- PostgreSQL 14+
- (Opcional) Active Directory / OpenLDAP para autenticação de usuários
- (Opcional) IA: servidor LLM (compatível com API do Ollama) **ou** engine local em Python — ver [docs/ia-hibrida.md](docs/ia-hibrida.md)
- (Opcional) Zabbix para integração de alarmes

### Backend

```bash
cd backend

# 1. Ambiente virtual
python -m venv ../venv
source ../venv/bin/activate     # Linux/Mac

# 2. Dependências
pip install -r requirements.txt

# 3. Configuração
cp .env.example .env            # edite com seus valores (ver seção abaixo)

# 4. Migrations (se usando Alembic)
alembic upgrade head

# 5. Servidor de desenvolvimento
uvicorn main:app --reload --host 0.0.0.0 --port 8000
```

- API: `http://localhost:8000`
- Swagger: `http://localhost:8000/docs`

**crypto_lock (obrigatório)**: o sistema cifra colunas sensíveis (ex.: segredo TOTP) com AES-256-GCM e fica bloqueado até o desbloqueio no boot. Gere o binário com os dados do proprietário:

```bash
# Defina em backend/.env:
#   SGTI_OWNER_NAME=<nome completo>
#   SGTI_OWNER_CPF=<cpf>
python build_crypto_lock.py
```

O desbloqueio acontece automaticamente no startup do `main.py`.

### Frontend

```bash
cd frontend
npm install
cp .env.example .env    # ajuste VITE_API_URL se necessário
npm run dev             # http://localhost:5173
```

### Variáveis de ambiente

**Backend (`backend/.env`)** — principais:

```env
DATABASE_URL=postgresql://cmdb:cmdb@localhost/cmdb
JWT_SECRET_KEY=your-secure-random-string
ACCESS_TOKEN_EXPIRE_MINUTES=30
REFRESH_TOKEN_EXPIRE_DAYS=7

# AD/LDAP
LDAP_BACKEND=ad            # ad (Active Directory) | openldap (slapd)
AD_SERVER=ldap://your-ad-server:389
AD_DOMAIN=YOUR.DOMAIN.COM
AD_BASE_DN=DC=your,DC=domain,DC=com

# Mapeamento de grupos AD → perfis da aplicação
ROLE_ADMIN=G_GESIN_GOSD_OMIS
ROLE_READ=G_GESIN

# Proprietário (crypto_lock)
SGTI_OWNER_NAME=<nome>
SGTI_OWNER_CPF=<cpf>

# IA — provider "llm" (opcional; provider "local" não precisa destes)
LLM_API_URL=http://localhost:11434

# IA — provider "local" (sentence-transformers em CPU, sem serviço externo)
AI_PROVIDER=llm            # llm | local
LOCAL_EMBED_MODEL=paraphrase-multilingual-MiniLM-L12-v2
# Instalação: pip install torch --index-url https://download.pytorch.org/whl/cpu
#             pip install sentence-transformers

# Zabbix (opcional)
ZABBIX_API_URL=http://zabbix/api_jsonrpc.php
```

**Frontend (`frontend/.env`)**:

```env
VITE_API_URL=http://localhost:8000
```

### Dados iniciais (seed)

```bash
set -a; source backend/.env; set +a       # Linux/Mac
PYTHONPATH=backend venv/bin/python scripts/seed.py
```

O seed popula dados mestre + ativos de exemplo + service account 'integracao-zabbix' e imprime o token da service account — guarde-o (header `X-Service-Token`).

### Populando dados de exemplo

Opcional: importa um dump de INSERTs (exportado do pgAdmin) com ativos e aplicações reais:

```bash
PYTHONPATH=backend venv/bin/python scripts/import_test_data.py /caminho/do/dump/ --dry-run   # simula
PYTHONPATH=backend venv/bin/python scripts/import_test_data.py /caminho/do/dump/             # grava

# Em seguida, gera mapa de TI por inferência:
PYTHONPATH=backend venv/bin/python scripts/infer_infra_map.py --token <service-token> --dry-run
PYTHONPATH=backend venv/bin/python scripts/infer_infra_map.py --token <service-token>

# Variante com IA local (reporta confiabilidade e abre reconciliação quando < 90%):
PYTHONPATH=backend venv/bin/python scripts/infer_infra_map_ia.py --token <service-token> --dry-run
```

Detalhes em [`docs/inferencias.md`](docs/inferencias.md).

### Testes

```bash
# Backend (usa SQLite de teste, env TESTING=1 automaticamente)
cd backend && TESTING=1 ../venv/bin/python -m pytest tests/ -q

# Frontend
cd frontend && npm run build
```

### Ambiente LDAP local (testes de autenticação)

```bash
cd backend/tests/ldap
docker compose up -d
./setup_ldap.sh
```

### Produção

1. `TESTING=0` em `backend/.env`
2. `JWT_SECRET_KEY` forte
3. PostgreSQL com pooling
4. Reverse proxy (nginx) com TLS
5. CORS restrito + rate limiting
6. Agregação de logs

---

## Estrutura do projeto

```
sgti/
├── backend/
│   ├── main.py                 # entrypoint FastAPI
│   ├── models.py               # models SQLAlchemy
│   ├── schemas.py              # schemas Pydantic
│   ├── database.py             # conexão/Session
│   ├── ai_engine.py            # engine de IA híbrida (providers llm/local)
│   ├── llm_client.py           # cliente LLM compatível com API do Ollama (provider "llm")
│   ├── crypto_guard.py         # cifra de colunas (crypto_lock)
│   ├── ldap_backend.py         # seletor AD/OpenLDAP
│   ├── routers/                # routers da API
│   │   ├── assets.py, ip_addresses.py, reference_data.py
│   │   ├── applications.py, relationships.py, infrastructure.py
│   │   ├── audit.py, integrations.py, auth.py, reconciliacoes.py
│   └── tests/
├── scripts/
│   ├── seed.py                 # dados mestre iniciais
│   ├── import_test_data.py     # importa dump de exemplo
│   ├── infer_infra_map.py      # inferência de mapa de TI (via API)
│   └── infer_infra_map_ia.py   # variante com LLM local (confiabilidade + reconciliação)
├── frontend/
│   └── src/
│       ├── views/              # telas (assets, infrastructure, admin...)
│       ├── components/         # componentes reutilizáveis
│       ├── stores/             # Pinia (auth)
│       ├── services/           # clientes API tipados
│       └── router/
├── docs/                       # documentação de funcionalidades
└── README.md
```

---

## Licença

Distribuído sob a GNU GENERAL PUBLIC LICENSE Version 3, 29 June 2007.
