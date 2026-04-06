from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager

from database import engine, Base

# routers
from routers import assets, relationships
from routers.services import router as services_router
from routers.tokens import router as tokens_router
from routers.audit import router as audit_router


# =========================
# DB INIT (SEM ALEMBIC)
# =========================

async def init_db():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)


@asynccontextmanager
async def lifespan(app: FastAPI):
    await init_db()
    yield


# =========================
# APP
# =========================

app = FastAPI(
    title="CMDB - Configuration Management Database",
    description="CMDB com suporte a grafo de dependências entre ativos",
    version="2.0.0",
    lifespan=lifespan
)


# =========================
# CORS
# =========================

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# =========================
# ROUTERS
# =========================

app.include_router(tokens_router)
app.include_router(assets.router)
app.include_router(relationships.router)
app.include_router(services_router)
app.include_router(audit_router)


# =========================
# HEALTH
# =========================

@app.get("/", tags=["Health"])
async def root():
    return {
        "message": "CMDB API",
        "status": "online",
        "version": "2.0.0",
        "docs": "/docs"
    }


@app.get("/health", tags=["Health"])
async def health():
    return {"status": "healthy"}