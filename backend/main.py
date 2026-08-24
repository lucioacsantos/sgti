from typing import Optional
from fastapi import FastAPI, Depends, HTTPException, Response, Request
from fastapi.responses import JSONResponse
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from starlette.exceptions import HTTPException as StarletteHTTPException
from sqlalchemy.orm import Session
from sqlalchemy import text
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded
import models, schemas
from routers import auth
from database import SessionLocal, engine
from sqlalchemy.exc import IntegrityError
from logging_config import setup_logging, get_logger
import logging

# Setup structured logging
setup_logging()
logger = get_logger(__name__)

# Inicializa o banco de dados (cria tabelas se não existirem)
models.Base.metadata.create_all(bind=engine)

# Rate limiter
limiter = Limiter(key_func=get_remote_address)

# Inicializa a aplicação FastAPI
app = FastAPI(
    title="SGTI ::: CMDB ::: API",
    version="2.0.0",
    description="API para gerenciamento de ativos de TI na CMDB do SGTI",
    server="SGTI"
)

# CORS Middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Configure for production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Rate limiting
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

# Dependência para obter o banco de dados
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

# Correlation ID middleware
@app.middleware("http")
async def add_correlation_id(request: Request, call_next):
    correlation_id = request.headers.get("X-Correlation-ID", "")
    if not correlation_id:
        import uuid
        correlation_id = str(uuid.uuid4())
    
    # Add to request state for logging
    request.state.correlation_id = correlation_id
    
    response = await call_next(request)
    response.headers["X-Correlation-ID"] = correlation_id
    return response


# GLOBAL EXCEPTION HANDLERS
@app.exception_handler(StarletteHTTPException)
async def http_exception_handler(request: Request, exc: StarletteHTTPException):
    logger.error(
        "HTTP exception",
        extra={
            "status_code": exc.status_code,
            "detail": exc.detail,
            "path": request.url.path,
            "method": request.method,
            "correlation_id": getattr(request.state, "correlation_id", ""),
        }
    )
    return JSONResponse(
        status_code=exc.status_code,
        content={"detail": exc.detail},
    )


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    logger.error(
        "Validation error",
        extra={
            "errors": exc.errors(),
            "path": request.url.path,
            "method": request.method,
            "correlation_id": getattr(request.state, "correlation_id", ""),
        }
    )
    return JSONResponse(
        status_code=422,
        content={"detail": "Validation error", "errors": exc.errors()},
    )


@app.exception_handler(Exception)
async def general_exception_handler(request: Request, exc: Exception):
    logger.exception(
        "Unhandled exception",
        extra={
            "path": request.url.path,
            "method": request.method,
            "error_type": type(exc).__name__,
            "correlation_id": getattr(request.state, "correlation_id", ""),
        }
    )
    return JSONResponse(
        status_code=500,
        content={"detail": "Internal server error"},
    )


# HEALTH
@app.get("/", tags=["Health"])
@limiter.limit("10/second")
async def root(request: Request):
    return {
        "message": "CMDB API",
        "status": "online",
        "version": "2.0.0",
        "docs": "/docs"
    }


@app.get("/health", tags=["Health"])
@limiter.limit("10/second")
async def health(request: Request, db: Session = Depends(get_db)):
    # Check database connectivity
    try:
        db.execute(text("SELECT 1"))
        db_status = "healthy"
    except Exception as e:
        logger.error("Health check DB failed", extra={"error": str(e)})
        db_status = "unhealthy"
    
    return {
        "status": "healthy" if db_status == "healthy" else "degraded",
        "database": db_status
    }


# Include routers
from routers import assets, ip_addresses, reference_data, applications, relationships, infrastructure, audit, integrations, auth

app.include_router(assets.router)
app.include_router(ip_addresses.router)
app.include_router(reference_data.router)
app.include_router(applications.router)
app.include_router(relationships.router)
app.include_router(relationships.rel_router)
app.include_router(infrastructure.cluster_router)
app.include_router(infrastructure.namespace_router)
app.include_router(infrastructure.servico_router)
app.include_router(infrastructure.servico_negocio_router)
app.include_router(infrastructure.instancia_router)
app.include_router(audit.router)
app.include_router(integrations.router)
app.include_router(integrations.zabbix_router)
app.include_router(auth.router)