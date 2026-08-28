from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from typing import Optional
import models, schemas, auth
from database import get_db
import logging

logger = logging.getLogger(__name__)

# ENDPOINTS DE CLUSTER
cluster_router = APIRouter(prefix="/clusters", tags=["Clusters"])


@cluster_router.post("/", response_model=schemas.ClusterResponse, status_code=201)
def create_cluster(
    cluster: schemas.ClusterCreate,
    db: Session = Depends(get_db),
    current_service: models.ServiceAccount = Depends(auth.get_current_actor)
):
    logger.info("Creating cluster", extra={"service_account": current_service.name, "cluster_nome": cluster.nome})
    if cluster.ativo_id:
        ativo_existe = db.query(models.Ativo).filter(models.Ativo.id == cluster.ativo_id).first()
        if not ativo_existe:
            raise HTTPException(status_code=404, detail=f"Ativo id={cluster.ativo_id} não encontrado")
    db_cluster = models.Cluster(**cluster.model_dump(exclude_unset=True))
    db.add(db_cluster)
    db.commit()
    db.refresh(db_cluster)
    return db_cluster


@cluster_router.get("/", response_model=list[schemas.ClusterResponse])
def read_clusters(
    db: Session = Depends(get_db),
    current_service: models.ServiceAccount = Depends(auth.get_current_actor)
):
    logger.debug("Listing clusters", extra={"service_account": current_service.name})
    return db.query(models.Cluster).all()


@cluster_router.get("/{cluster_id}", response_model=schemas.ClusterResponse)
def read_cluster(
    cluster_id: int,
    db: Session = Depends(get_db),
    current_service: models.ServiceAccount = Depends(auth.get_current_actor)
):
    logger.debug("Reading cluster", extra={"service_account": current_service.name, "cluster_id": cluster_id})
    cluster = db.query(models.Cluster).filter(models.Cluster.id == cluster_id).first()
    if not cluster:
        raise HTTPException(status_code=404, detail="Cluster não encontrado")
    return cluster


# ENDPOINTS DE NAMESPACE
namespace_router = APIRouter(prefix="/namespaces", tags=["Namespaces"])


@namespace_router.post("/", response_model=schemas.NamespaceResponse, status_code=201)
def create_namespace(
    namespace: schemas.NamespaceCreate,
    db: Session = Depends(get_db),
    current_service: models.ServiceAccount = Depends(auth.get_current_actor)
):
    logger.info("Creating namespace", extra={"service_account": current_service.name, "namespace_nome": namespace.nome})
    if namespace.cluster_id:
        cluster_existe = db.query(models.Cluster).filter(models.Cluster.id == namespace.cluster_id).first()
        if not cluster_existe:
            raise HTTPException(status_code=404, detail=f"Cluster id={namespace.cluster_id} não encontrado")
    if namespace.ativo_id:
        ativo_existe = db.query(models.Ativo).filter(models.Ativo.id == namespace.ativo_id).first()
        if not ativo_existe:
            raise HTTPException(status_code=404, detail=f"Ativo id={namespace.ativo_id} não encontrado")
    db_namespace = models.Namespace(**namespace.model_dump(exclude_unset=True))
    db.add(db_namespace)
    db.commit()
    db.refresh(db_namespace)
    return db_namespace


@namespace_router.get("/", response_model=list[schemas.NamespaceResponse])
def read_namespaces(
    db: Session = Depends(get_db),
    current_service: models.ServiceAccount = Depends(auth.get_current_actor)
):
    logger.debug("Listing namespaces", extra={"service_account": current_service.name})
    return db.query(models.Namespace).all()


@namespace_router.get("/{namespace_id}", response_model=schemas.NamespaceResponse)
def read_namespace(
    namespace_id: int,
    db: Session = Depends(get_db),
    current_service: models.ServiceAccount = Depends(auth.get_current_actor)
):
    logger.debug("Reading namespace", extra={"service_account": current_service.name, "namespace_id": namespace_id})
    namespace = db.query(models.Namespace).filter(models.Namespace.id == namespace_id).first()
    if not namespace:
        raise HTTPException(status_code=404, detail="Namespace não encontrado")
    return namespace


# ENDPOINTS DE SERVIÇO
servico_router = APIRouter(prefix="/servicos", tags=["Serviços"])


@servico_router.post("/", response_model=schemas.ServicoResponse, status_code=201)
def create_servico(
    servico: schemas.ServicoCreate,
    db: Session = Depends(get_db),
    current_service: models.ServiceAccount = Depends(auth.get_current_actor)
):
    logger.info("Creating service", extra={"service_account": current_service.name, "servico_nome": servico.nome})
    if servico.ativo_id:
        ativo_existe = db.query(models.Ativo).filter(models.Ativo.id == servico.ativo_id).first()
        if not ativo_existe:
            raise HTTPException(status_code=404, detail=f"Ativo id={servico.ativo_id} não encontrado")
    db_servico = models.Servico(**servico.model_dump(exclude_unset=True))
    db.add(db_servico)
    db.commit()
    db.refresh(db_servico)
    return db_servico


@servico_router.get("/", response_model=list[schemas.ServicoResponse])
def read_servicos(
    db: Session = Depends(get_db),
    current_service: models.ServiceAccount = Depends(auth.get_current_actor)
):
    logger.debug("Listing services", extra={"service_account": current_service.name})
    return db.query(models.Servico).all()


@servico_router.get("/{servico_id}", response_model=schemas.ServicoResponse)
def read_servico(
    servico_id: int,
    db: Session = Depends(get_db),
    current_service: models.ServiceAccount = Depends(auth.get_current_actor)
):
    logger.debug("Reading service", extra={"service_account": current_service.name, "servico_id": servico_id})
    servico = db.query(models.Servico).filter(models.Servico.id == servico_id).first()
    if not servico:
        raise HTTPException(status_code=404, detail="Serviço não encontrado")
    return servico


# ENDPOINTS DE SERVIÇO NEGÓCIO
servico_negocio_router = APIRouter(prefix="/servicos-negocio", tags=["Serviços de Negócio"])


@servico_negocio_router.post("/", response_model=schemas.ServicoNegocioResponse, status_code=201)
def create_servico_negocio(
    servico: schemas.ServicoNegocioCreate,
    db: Session = Depends(get_db),
    current_service: models.ServiceAccount = Depends(auth.get_current_actor)
):
    logger.info("Creating business service", extra={"service_account": current_service.name, "name": servico.nome})
    if servico.ativo_id:
        ativo_existe = db.query(models.Ativo).filter(models.Ativo.id == servico.ativo_id).first()
        if not ativo_existe:
            raise HTTPException(status_code=404, detail=f"Ativo id={servico.ativo_id} não encontrado")
    db_servico = models.ServicoNegocio(**servico.model_dump(exclude_unset=True))
    db.add(db_servico)
    db.commit()
    db.refresh(db_servico)
    return db_servico


@servico_negocio_router.get("/", response_model=list[schemas.ServicoNegocioResponse])
def read_servicos_negocio(
    db: Session = Depends(get_db),
    current_service: models.ServiceAccount = Depends(auth.get_current_actor)
):
    logger.debug("Listing business services", extra={"service_account": current_service.name})
    return db.query(models.ServicoNegocio).all()


@servico_negocio_router.get("/{servico_id}", response_model=schemas.ServicoNegocioResponse)
def read_servico_negocio(
    servico_id: int,
    db: Session = Depends(get_db),
    current_service: models.ServiceAccount = Depends(auth.get_current_actor)
):
    logger.debug("Reading business service", extra={"service_account": current_service.name, "servico_id": servico_id})
    servico = db.query(models.ServicoNegocio).filter(models.ServicoNegocio.id == servico_id).first()
    if not servico:
        raise HTTPException(status_code=404, detail="Serviço de negócio não encontrado")
    return servico


# ENDPOINTS DE INSTÂNCIA APLICAÇÃO
instancia_router = APIRouter(prefix="/instancias-aplicacao", tags=["Instâncias de Aplicação"])


@instancia_router.post("/", response_model=schemas.InstanciaAplicacaoResponse, status_code=201)
def create_instancia_aplicacao(
    instancia: schemas.InstanciaAplicacaoCreate,
    db: Session = Depends(get_db),
    current_service: models.ServiceAccount = Depends(auth.get_current_actor)
):
    logger.info("Creating application instance", extra={"service_account": current_service.name, "aplicacao_id": instancia.aplicacao_id})
    aplicacao = db.query(models.Aplicacao).filter(models.Aplicacao.id == instancia.aplicacao_id).first()
    if not aplicacao:
        raise HTTPException(status_code=404, detail=f"Aplicação id={instancia.aplicacao_id} não encontrada")
    if instancia.ativo_id:
        ativo_existe = db.query(models.Ativo).filter(models.Ativo.id == instancia.ativo_id).first()
        if not ativo_existe:
            raise HTTPException(status_code=404, detail=f"Ativo id={instancia.ativo_id} não encontrado")
    db_instancia = models.InstanciaAplicacao(**instancia.model_dump(exclude_unset=True))
    db.add(db_instancia)
    db.commit()
    db.refresh(db_instancia)
    return db_instancia


@instancia_router.get("/", response_model=list[schemas.InstanciaAplicacaoResponse])
def read_instancias_aplicacao(
    aplicacao_id: Optional[int] = None,
    db: Session = Depends(get_db),
    current_service: models.ServiceAccount = Depends(auth.get_current_actor)
):
    logger.debug("Listing application instances", extra={"service_account": current_service.name, "aplicacao_id": aplicacao_id})
    query = db.query(models.InstanciaAplicacao)
    if aplicacao_id:
        query = query.filter(models.InstanciaAplicacao.aplicacao_id == aplicacao_id)
    return query.all()


@instancia_router.get("/{instancia_id}", response_model=schemas.InstanciaAplicacaoResponse)
def read_instancia_aplicacao(
    instancia_id: int,
    db: Session = Depends(get_db),
    current_service: models.ServiceAccount = Depends(auth.get_current_actor)
):
    logger.debug("Reading application instance", extra={"service_account": current_service.name, "instancia_id": instancia_id})
    instancia = db.query(models.InstanciaAplicacao).filter(models.InstanciaAplicacao.id == instancia_id).first()
    if not instancia:
        raise HTTPException(status_code=404, detail="Instância de aplicação não encontrada")
    return instancia