# SGTI CMDB Prototype

Sistema de Gerenciamento de TI - Configuration Management Database prototype with FastAPI backend and React frontend.

## Features

### Backend (FastAPI 2.0.0)

**Core Architecture**
- Modular routers: Assets, IP Addresses, Reference Data, Applications, Relationships, Infrastructure, Audit, Integrations, Auth
- PostgreSQL with SQLAlchemy ORM (production), SQLite for tests
- JWT authentication with service account tokens (API) + AD/LDAP + refresh tokens (users)
- Role-based access: admin, analyst, reviewer, reconciliator, revisor, viewer
- Audit logging on all CRUD operations with correlation IDs
- Rate limiting (100 req/min per IP) + CORS + security headers

**Data Models**
| Entity | Description |
|--------|-------------|
| `Ativo` | Core asset (host/server) with tipo, ambiente, status, criticidade, SO, area, hardware specs |
| `EnderecoIp` | IP addresses with upsert (IPv4/IPv6, primary, interface, tipo) |
| `Relacionamento` | Asset-to-asset connections with typed relationships |
| `TipoRelacionamento` | Relationship types (depends on, contains, connects to) |
| Reference data | Asset types, environments, statuses, criticidades, OS, areas |
| Infrastructure | Clusters, Namespaces, Serviços, Serviços de Negócio, App Instances |

**API Endpoints**
- **Assets**: CRUD + upsert by nome, pagination, search
- **IPs**: Upsert (create/update by ativo_id+ip), list by ativo
- **Relationships**: Full CRUD + typed relationship management
- **Reference Data**: Read-only lists + admin CRUD for all reference tables
- **Infrastructure**: Clusters, Namespaces, Services, Business Services, App Instances
- **Audit**: Paginated logs filtered by entity/entity_id
- **Integrations**: Zabbix webhook, Ollama AI queries

### Integrations

| Integration | Purpose | Implementation |
|-------------|---------|----------------|
| **Active Directory** | User auth + group sync | `ad_auth.py` with LDAP3, JWT tokens, 2FA (TOTP) |
| **Zabbix** | Alarm enrichment | Webhook receiver (`/integrations/zabbix/alarm`) + Ollama AI analysis |
| **Ollama (LLM)** | AI-powered alarm analysis | Local LLM for root cause suggestions |
| **Data Collection** | External source ingestion | Separate API (`/data-collection`) for sources, jobs, reconciliation, certification |

**Data Collection Pipeline**
- Sources (vCenter, Satellite, AD, etc.) → Collection Jobs → Entities → Reconciliation Sessions → Conflicts → Certification Workflow (Analyst → Reviewer)

### Frontend (React 18 + TypeScript + Vite)

**Tech Stack**
- **State**: Zustand (auth) + TanStack Query (server state)
- **UI**: Tailwind CSS + Headless UI patterns + Lucide icons
- **Forms**: React Hook Form + Zod validation
- **Routing**: React Router v6 with protected routes

**Pages & Features**

| Module | Pages | Key Features |
|--------|-------|--------------|
| **Dashboard** | `/` | Stats cards, recent assets/jobs, quick actions, alerts |
| **Inventory** | `/hosts`, `/relationships`, `/applications`, `/clusters`, `/namespaces`, `/services` | Searchable tables, filters, pagination, CRUD modals |
| **Reconciliation** | `/reconciliation`, `/reconciliation/:id` | Session management, conflict visualization, progress tracking |
| **Certification** | `/certification`, `/certification/:id` | Queue with role-based views (analyst/reviewer), approve/reject, comments |
| **Admin** | `/admin/*` | Users, relationship types, asset types, environments, statuses, criticidades, OS, areas |
| **Auth** | `/login`, `/2fa/verify`, `/2fa/setup` | AD login, TOTP 2FA setup/verification |
| **Profile** | `/profile` | Profile edit, password change, 2FA management |

**Authentication Flow**
1. User enters AD credentials → `/auth/ad/login`
2. If 2FA required → redirect to `/2fa/verify`
3. TOTP code verified → JWT access + refresh tokens stored
4. `AuthProvider` auto-refreshes on expiry
5. Role-based UI rendering (admin sees admin menu, analyst sees certification queue)

**API Layer** (`lib/api.ts`)
- Two axios instances: `api` (main) + `dataCollectionApi`
- Request interceptor adds Bearer token
- Response interceptor handles 401 → token refresh → retry
- Typed API clients for each domain with `.then(res => res.data)` unwrapping

### Configuration Files

| File | Purpose |
|------|---------|
| `.env` | All secrets: DB, JWT, AD, Ollama, Zabbix, API URLs |
| `.eslintrc.cjs` | Linting with React/TS rules (relaxed for legacy) |
| `backend/.env` | Backend-specific (loaded by FastAPI) |
| `frontend/.env` | `VITE_API_URL`, `VITE_DATA_COLLECTION_URL` |

### Testing
- **Backend**: 32 pytest tests covering assets, auth, IPs, relationships, audit, infrastructure
- **Local LDAP Test Env**: Dockerized OpenLDAP for authentication testing
  ```bash
  cd backend/tests/ldap
  docker compose up -d
  ./setup_ldap.sh
  ```
- **Test DB**: SQLite in-memory with dependency override
- **Auth**: Service account token fixture for all API tests

### Key Design Patterns
- **Upsert patterns** for idempotent data collection (assets by nome, IPs by ativo_id+ip)
- **Service account auth** for machine-to-machine (collection agents)
- **User auth** via AD + JWT for UI
- **Admin endpoints** under `/admin/*` with role checks
- **Correlation IDs** on all requests for tracing
- **Structured logging** with service account context

---

## Installation & Run Instructions

### Prerequisites
- Python 3.12+
- Node.js 18+
- PostgreSQL 14+
- (Optional) Active Directory / LDAP server
- (Optional) Ollama for AI features
- (Optional) Zabbix for alarm integration

### Backend Setup

```bash
cd backend

# Create virtual environment
python -m venv venv
source venv/bin/activate  # Linux/Mac
# venv\Scripts\activate   # Windows

# Install dependencies
pip install -r requirements.txt

# Configure environment
cp .env.example .env  # Edit with your values

# Run database migrations (if using Alembic)
# alembic upgrade head

# Start development server
uvicorn main:app --reload --host 0.0.0.0 --port 8000
```

Backend runs at `http://localhost:8000`
API docs at `http://localhost:8000/docs`

### Frontend Setup

```bash
cd frontend

# Install dependencies
npm install

# Configure environment
cp .env.example .env  # Edit VITE_API_URL if needed

# Start development server
npm run dev
```

Frontend runs at `http://localhost:5173`

### Docker Compose (Full Stack)

```bash
# From project root
docker-compose up -d

# Services:
# - postgres:5432
# - backend:8000
# - frontend:5173
# - ollama:11434 (optional)
```

### Environment Variables

**Backend (`.env`)**
```env
# Database
DATABASE_URL=postgresql://cmdb:cmdb@localhost/cmdb

# JWT
JWT_SECRET_KEY=your-secure-random-string
ALGORITHM=HS256
ACCESS_TOKEN_EXPIRE_MINUTES=30
REFRESH_TOKEN_EXPIRE_DAYS=7

# AD/LDAP
AD_SERVER=ldap://your-ad-server:389
AD_PORT=389
AD_DOMAIN=YOUR.DOMAIN.COM
AD_BASE_DN=DC=your,DC=domain,DC=com
AD_USE_SSL=false

# Role Mappings (Group Name = Application Role)
ROLE_ADMIN=G_GESIN_GOSD_OMIS
ROLE_READ=G_GESIN

# Ollama
OLLAMA_API_URL=http://localhost:11434/api/generate
OLLAMA_MODEL=llama3

# Zabbix
ZABBIX_API_URL=http://zabbix/api_jsonrpc.php
ZABBIX_API_TOKEN=your-token
```

**Frontend (`.env`)**
```env
VITE_API_URL=http://localhost:8000/api
VITE_DATA_COLLECTION_URL=http://localhost:8000/data-collection
```

### Running Tests

```bash
# Backend tests
cd backend
source venv/bin/activate
pytest tests/ -v

# Frontend lint
cd frontend
npm run lint

# Frontend build
npm run build
```

### Production Deployment

1. Set `TESTING=0` in backend `.env`
2. Use strong `JWT_SECRET_KEY`
3. Configure PostgreSQL with connection pooling
4. Run behind reverse proxy (nginx) with TLS
5. Set secure CORS origins
6. Enable rate limiting middleware
7. Configure log aggregation

### Default Credentials

For testing with service accounts:
```bash
# Header: X-Service-Token: test-token-123
# Creates test service account automatically in test environment
```

For AD users: Use your domain credentials. First login creates user record with roles from AD groups.

---

## Project Structure

```
sgti/
├── backend/
│   ├── main.py              # FastAPI app entry point
│   ├── models.py            # SQLAlchemy models
│   ├── schemas.py           # Pydantic schemas
│   ├── database.py          # DB connection
│   ├── ad_auth.py           # AD/LDAP + JWT + 2FA
│   ├── routers/             # API routers
│   │   ├── assets.py
│   │   ├── ip_addresses.py
│   │   ├── reference_data.py
│   │   ├── relationships.py
│   │   ├── infrastructure.py
│   │   ├── audit.py
│   │   ├── integrations.py
│   │   └── auth.py
│   ├── tests/               # Pytest suite
│   └── requirements.txt
├── frontend/
│   ├── src/
│   │   ├── pages/           # Page components
│   │   ├── components/      # Reusable components
│   │   ├── store/           # Zustand stores
│   │   ├── lib/             # API clients
│   │   └── main.tsx         # App entry
│   ├── package.json
│   └── vite.config.ts
├── .env                     # Root environment
├── docker-compose.yml
└── README.md
```

---

## License

Internal prototype - SGTI