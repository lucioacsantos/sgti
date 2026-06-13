from fastapi import FastAPI, Depends, HTTPException
from sqlalchemy.orm import Session
import models, schemas, auth, zabbix
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

# ENDPOINTS DE DADOS AUXILIARES
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

@app.post("/sistema-operacional/", response_model=schemas.SistemaOperacionalResponse, status_code=201)
def create_sistema_operacional(
    sistema_operacional: schemas.SistemaOperacionalCreate, 
    db: Session = Depends(get_db)#,
    #current_service: models.ServiceAccount = Depends(auth.get_service_account)
    ):
    #print(f"Ação realizada pela service account: {current_service.name}")
    db_sistema_operacional = models.SistemaOperacional(**sistema_operacional.model_dump())
    db.add(db_sistema_operacional)
    db.commit()
    db.refresh(db_sistema_operacional)
    return db_sistema_operacional

@app.get("/sistema-operacional/", response_model=list[schemas.SistemaOperacionalResponse])
def read_sistemas_operacionais(db: Session = Depends(get_db)):
    sistemas_operacionais = db.query(models.SistemaOperacional).all()
    return sistemas_operacionais

@app.get("/areas/", response_model=list[schemas.AreasResponse])
def read_areas(db: Session = Depends(get_db)):
    areas = db.query(models.Areas).all()
    return areas

# ENDPOINTS DE APLICAÇÕES
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

# ENDPOINTS DE INTEGRAÇÃO COM OLLAMA
@app.post("/ollama/", response_model=schemas.OllamaResponse)
def ask_ollama(
    question: schemas.OllamaRequest, 
    current_service: models.ServiceAccount = Depends(auth.get_service_account)
    ):
    print(f"Ação realizada pela service account: {current_service.name}")
    response = auth.ask_ollama(question.question, question.model)
    return {"response": response}

@app.post("/zabbix/alarmes/observacao-ollama/", response_model=schemas.ZabbixOllamaObservationResponse)
def add_ollama_response_to_zabbix_alarm(
    payload: schemas.ZabbixOllamaObservationRequest,
    current_service: models.ServiceAccount = Depends(auth.get_service_account)
):
    print(f"Ação realizada pela service account: {current_service.name}")
    zabbix_client = zabbix.ZabbixClient()
    problem = zabbix_client.get_open_problem(payload.event_id)
    ollama_prompt = (
        "Analise o alarme aberto do Zabbix abaixo e gere uma observação objetiva "
        "para registrar no próprio alarme.\n\n"
        f"Event ID: {payload.event_id}\n"
        f"Nome do problema: {problem.get('name')}\n"
        f"Severidade: {problem.get('severity')}\n"
        f"Object ID: {problem.get('objectid')}\n\n"
        f"Solicitação: {payload.question}"
    )
    ollama_response = auth.ask_ollama(ollama_prompt, payload.model)
    zabbix_result = zabbix_client.add_event_observation(payload.event_id, ollama_response)

    return {
        "event_id": payload.event_id,
        "problem_name": problem.get("name"),
        "ollama_response": ollama_response,
        "zabbix_result": zabbix_result,
    }
