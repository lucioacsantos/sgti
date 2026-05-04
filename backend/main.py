from fastapi import FastAPI, Depends, HTTPException
from sqlalchemy.orm import Session
import models, schemas, auth
from database import SessionLocal, engine

models.Base.metadata.create_all(bind=engine)

app = FastAPI(
    title="SGTI ::: CMDB ::: API", 
    version="1.0", 
    description="API para gerenciamento de ativos de TI na CMDB do SGTI", 
    server="SGTI"
    )

# Dependência para obter o banco de dados
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

# HEALTH
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

# ENDPOINTS DE ATIVOS
@app.post("/ativos/", response_model=schemas.AtivoResponse, status_code=201)
def create_ativo(
    ativo: schemas.AtivoCreate, 
    db: Session = Depends(get_db),
    current_service: models.ServiceAccount = Depends(auth.get_service_account)
    ):
    print(f"Ação realizada pela service account: {current_service.name}")
    db_ativo = models.Ativo(**ativo.model_dump())
    db.add(db_ativo)
    db.commit()
    db.refresh(db_ativo)
    return db_ativo

@app.get("/ativos/", response_model=list[schemas.AtivoResponse])
def read_ativos(
    skip: int = 0, 
    limit: int = 100, 
    db: Session = Depends(get_db),
    current_service: models.ServiceAccount = Depends(auth.get_service_account)
    ):
    ativos = db.query(models.Ativo).offset(skip).limit(limit).all()
    return ativos

@app.get("/ativos/{ativo_id}", response_model=schemas.AtivoResponse)
def read_ativo(ativo_id: int, db: Session = Depends(get_db)):
    db_ativo = db.query(models.Ativo).filter(models.Ativo.id == ativo_id).first()
    if db_ativo is None:
        raise HTTPException(status_code=404, detail="Ativo não encontrado")
    return db_ativo

@app.get("/tipos-ativos/", response_model=list[schemas.TipoAtivoResponse])
def read_tipos_ativos(db: Session = Depends(get_db)):
    tipos_ativos = db.query(models.TipoAtivo).all()
    return tipos_ativos

@app.get("/status-ativos/", response_model=list[schemas.StatusAtivoResponse])
def read_status_ativos(db: Session = Depends(get_db)):
    status_ativos = db.query(models.StatusAtivo).all()
    return status_ativos

@app.get("/ambientes/", response_model=list[schemas.AmbienteResponse])
def read_ambientes(db: Session = Depends(get_db)):
    ambientes = db.query(models.Ambiente).all()
    return ambientes

@app.get("/criticidades/", response_model=list[schemas.CriticidadeResponse])
def read_criticidades(db: Session = Depends(get_db)):
    criticidades = db.query(models.Criticidade).all()
    return criticidades

@app.get("/sistema-operacional/", response_model=list[schemas.SistemaOperacionalResponse])
def read_sistemas_operacionais(db: Session = Depends(get_db)):
    sistemas_operacionais = db.query(models.SistemaOperacional).all()
    return sistemas_operacionais

@app.post("/aplicacoes/", response_model=schemas.AplicacaoResponse, status_code=201)
def create_aplicacao(
    aplicacao: schemas.AplicacaoCreate, 
    db: Session = Depends(get_db)#,
    #current_service: models.ServiceAccount = Depends(auth.get_service_account)
    ):
    #print(f"Ação realizada pela service account: {current_service.name}")
    db_aplicacao = models.Aplicacao(**aplicacao.model_dump())
    db.add(db_aplicacao)
    db.commit()
    db.refresh(db_aplicacao)
    return db_aplicacao

@app.get("/aplicacoes/", response_model=list[schemas.AplicacaoResponse])
def read_aplicacoes(db: Session = Depends(get_db)):
    aplicacoes = db.query(models.Aplicacao).all()
    return aplicacoes