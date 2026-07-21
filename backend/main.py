from typing import Optional
from fastapi import FastAPI, Depends, HTTPException, Response
from sqlalchemy.orm import Session
import models, schemas, auth, zabbix
from database import SessionLocal, engine
from sqlalchemy import func
from sqlalchemy.exc import IntegrityError

# Inicializa o banco de dados (cria tabelas se não existirem)
models.Base.metadata.create_all(bind=engine)

# Inicializa a aplicação FastAPI
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
    
    # 🔒 Verificação de duplicidade (case-insensitive)
    existente = db.query(models.Ativo).filter(
        db.func.lower(models.Ativo.nome) == ativo.nome.lower()
    ).first()
    
    if existente:
        raise HTTPException(
            status_code=409,
            detail=f"Ativo com nome '{ativo.nome}' já existe (id={existente.id})"
        )
    
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

@app.put("/ativos/{nome}", response_model=schemas.AtivoResponse)
def upsert_ativo(
    nome: str,
    ativo: schemas.AtivoUpdate,
    response: Response,
    db: Session = Depends(get_db),
    current_service: models.ServiceAccount = Depends(auth.get_service_account)
    ):

    print(f"Ação realizada pela service account: {current_service.name}")

    db_ativo = db.query(models.Ativo).filter(
        func.lower(models.Ativo.nome) == nome.lower()
    ).first()

    dados = ativo.model_dump(exclude_unset=True)

    if db_ativo:
        for campo, valor in dados.items():
            setattr(db_ativo, campo, valor)
        db.commit()
        db.refresh(db_ativo)
        response.status_code = 200
        return db_ativo

    dados.setdefault("nome", nome)

    try:
        novo = models.Ativo(**dados)
        db.add(novo)
        db.commit()
        db.refresh(novo)
        response.status_code = 201
        return novo
    except IntegrityError:
        db.rollback()
        # Race condition: outro processo criou entre a consulta e a inserção
        db_ativo = db.query(models.Ativo).filter(
            func.lower(models.Ativo.nome) == nome.lower()
        ).first()
        # Atualiza o que o outro processo acabou de criar
        for campo, valor in dados.items():
            setattr(db_ativo, campo, valor)
        db.commit()
        db.refresh(db_ativo)
        response.status_code = 200
        return db_ativo

@app.get("/ativos/{nome}", response_model=schemas.AtivoResponse)
def read_ativo(nome: str, db: Session = Depends(get_db)):
    db_ativo = db.query(models.Ativo).filter(
        func.lower(models.Ativo.nome) == nome.lower()
    ).first()
    if db_ativo is None:
        raise HTTPException(status_code=404, detail="Ativo não encontrado")
    return db_ativo

@app.put("/enderecos-ip/", response_model=schemas.EnderecoIpResponse)
def upsert_endereco_ip(
    payload: schemas.EnderecoIpUpsert,
    response: Response,
    db: Session = Depends(get_db),
    current_service: models.ServiceAccount = Depends(auth.get_service_account)
    ):
    print(f"Ação realizada pela service account: {current_service.name}")

    # Verifica se o ativo existe (evita erro de FK confuso)
    ativo_existe = db.query(models.Ativo).filter(models.Ativo.id == payload.ativo_id).first()
    if not ativo_existe:
        raise HTTPException(status_code=404, detail=f"Ativo id={payload.ativo_id} não encontrado")

    dados = payload.model_dump(exclude_unset=True)

    # Busca registro existente pela chave natural (ativo_id, ip)
    db_ip = db.query(models.EnderecoIp).filter(
        models.EnderecoIp.ativo_id == payload.ativo_id,
        models.EnderecoIp.ip == payload.ip
    ).first()

    # Se marcado como primário, desmarca os demais IPs do mesmo ativo
    if dados.get("primario"):
        db.query(models.EnderecoIp).filter(
            models.EnderecoIp.ativo_id == payload.ativo_id,
            models.EnderecoIp.id != (db_ip.id if db_ip else None)
        ).update({"primario": False})

    if db_ip:
        for campo, valor in dados.items():
            setattr(db_ip, campo, valor)
        db.commit()
        db.refresh(db_ip)
        response.status_code = 200
        return db_ip

    try:
        novo = models.EnderecoIp(**dados)
        db.add(novo)
        db.commit()
        db.refresh(novo)
        response.status_code = 201
        return novo
    except IntegrityError:
        db.rollback()
        # Race condition: outro processo inseriu entre a consulta e o insert
        db_ip = db.query(models.EnderecoIp).filter(
            models.EnderecoIp.ativo_id == payload.ativo_id,
            models.EnderecoIp.ip == payload.ip
        ).first()
        for campo, valor in dados.items():
            setattr(db_ip, campo, valor)
        db.commit()
        db.refresh(db_ip)
        response.status_code = 200
        return db_ip

@app.get("/enderecos-ip/", response_model=list[schemas.EnderecoIpResponse])
def read_enderecos_ip(
    ativo_id: Optional[int] = None,
    skip: int = 0,
    limit: int = 100,
    db: Session = Depends(get_db),
    current_service: models.ServiceAccount = Depends(auth.get_service_account)
    ):
    query = db.query(models.EnderecoIp)
    if ativo_id:
        query = query.filter(models.EnderecoIp.ativo_id == ativo_id)
    return query.offset(skip).limit(limit).all()


@app.delete("/enderecos-ip/{ip_id}", status_code=204)
def delete_endereco_ip(
    ip_id: int,
    db: Session = Depends(get_db),
    current_service: models.ServiceAccount = Depends(auth.get_service_account)
    ):
    db_ip = db.query(models.EnderecoIp).filter(models.EnderecoIp.id == ip_id).first()
    if not db_ip:
        raise HTTPException(status_code=404, detail="Endereço IP não encontrado")
    db.delete(db_ip)
    db.commit()

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
