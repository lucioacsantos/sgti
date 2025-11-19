from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
from database import init_db
from routers import assets, relationships

@asynccontextmanager
async def lifespan(app: FastAPI):
    await init_db()
    yield

app = FastAPI(
    title="CMDB - Configuration Management Database",
    description="Sistema de gerenciamento de ativos de TI com suporte a relacionamentos entre itens de configuração",
    version="1.0.0",
    lifespan=lifespan
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(assets.router)
app.include_router(relationships.router)

@app.get("/", tags=["Health"])
async def root():
    return {
        "message": "CMDB API - Configuration Management Database",
        "docs": "/docs",
        "status": "online"
    }

@app.get("/health", tags=["Health"])
async def health_check():
    return {"status": "healthy"}
