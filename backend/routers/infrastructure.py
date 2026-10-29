# Objetivo: CRUD idempotente e auditado de clusters, namespaces, serviços, serviços de negócio e instâncias de aplicação.
# Author: Lucio A C Santos — GitHub: https://github.com/lucioacsantos

from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlalchemy.orm import Session
from sqlalchemy import func
from typing import Optional
import models, schemas, auth, audit
from database import get_db
import logging

logger = logging.getLogger(__name__)


def _require_admin(current_service: models.ServiceAccount) -> None:
    """Verifica se o ator (usuário AD) possui perfil admin."""
    import json
    try:
        user_data = json.loads(current_service.token_hash)
        roles = user_data.get("roles", [])
    except Exception:
        roles = []
    if "admin" not in roles:
        raise HTTPException(status_code=403, detail="Required role(s): ['admin']")


def _audit_change(db: Session, entidade: str, entidade_id, acao: str,
                  antes=None, depois=None, usuario: str = None) -> None:
    try:
        audit.create_audit_log(
            db=db, entidade=entidade, entidade_id=entidade_id, acao=acao,
            antes=antes, depois=depois, usuario=usuario)
        db.commit()
    except Exception:
        logger.warning("Falha ao gravar audit log", exc_info=True)


# ENDPOINTS DE CLUSTER
cluster_router = APIRouter(prefix="/clusters", tags=["Clusters"])


@cluster_router.post("/", response_model=schemas.ClusterResponse, status_code=201)
def create_cluster(
    cluster: schemas.ClusterCreate,
    response: Response,
    db: Session = Depends(get_db),
    current_service: models.ServiceAccount = Depends(auth.get_current_actor)
):
    logger.info("Upserting cluster", extra={"service_account": current_service.name, "cluster_nome": cluster.nome})
    if cluster.ativo_id:
        ativo_existe = db.query(models.Ativo).filter(models.Ativo.id == cluster.ativo_id).first()
        if not ativo_existe:
            raise HTTPException(status_code=404, detail=f"Ativo id={cluster.ativo_id} não encontrado")

    dados = cluster.model_dump(exclude_unset=True)
    existente = db.query(models.Cluster).filter(
        func.lower(models.Cluster.nome) == cluster.nome.strip().lower()
    ).first()

    if existente:
        antes = audit.model_to_dict(existente)
        for campo, valor in dados.items():
            setattr(existente, campo, valor)
        db.commit()
        db.refresh(existente)
        _audit_change(db, "cluster", existente.id, "UPDATE", antes=antes,
                      depois=audit.model_to_dict(existente), usuario=current_service.name)
        response.status_code = 200
        return existente

    db_cluster = models.Cluster(**dados)
    db.add(db_cluster)
    db.commit()
    db.refresh(db_cluster)
    _audit_change(db, "cluster", db_cluster.id, "CREATE",
                  depois=audit.model_to_dict(db_cluster), usuario=current_service.name)
    response.status_code = 201
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


@cluster_router.put("/{cluster_id}", response_model=schemas.ClusterResponse)
def update_cluster(
    cluster_id: int,
    cluster: schemas.ClusterCreate,
    db: Session = Depends(get_db),
    current_service: models.ServiceAccount = Depends(auth.get_current_actor)
):
    """Atualiza um cluster (correção manual — perfil admin)."""
    _require_admin(current_service)
    db_cluster = db.query(models.Cluster).filter(models.Cluster.id == cluster_id).first()
    if not db_cluster:
        raise HTTPException(status_code=404, detail="Cluster não encontrado")

    dados = cluster.model_dump(exclude_unset=True)
    if "ativo_id" in dados and dados["ativo_id"]:
        if not db.query(models.Ativo).filter(models.Ativo.id == dados["ativo_id"]).first():
            raise HTTPException(status_code=404, detail=f"Ativo id={dados['ativo_id']} não encontrado")

    antes = audit.model_to_dict(db_cluster)
    for campo, valor in dados.items():
        setattr(db_cluster, campo, valor)
    db.commit()
    db.refresh(db_cluster)
    _audit_change(db, "cluster", db_cluster.id, "UPDATE", antes=antes,
                  depois=audit.model_to_dict(db_cluster), usuario=current_service.name)
    logger.info("Updating cluster", extra={"service_account": current_service.name, "cluster_id": cluster_id})
    return db_cluster


@cluster_router.delete("/{cluster_id}", status_code=204)
def delete_cluster(
    cluster_id: int,
    db: Session = Depends(get_db),
    current_service: models.ServiceAccount = Depends(auth.get_current_actor)
):
    """Exclui um cluster (correção manual — perfil admin)."""
    _require_admin(current_service)
    db_cluster = db.query(models.Cluster).filter(models.Cluster.id == cluster_id).first()
    if not db_cluster:
        raise HTTPException(status_code=404, detail="Cluster não encontrado")

    antes = audit.model_to_dict(db_cluster)
    db.delete(db_cluster)
    db.commit()
    _audit_change(db, "cluster", cluster_id, "DELETE", antes=antes, usuario=current_service.name)
    logger.info("Deleting cluster", extra={"service_account": current_service.name, "cluster_id": cluster_id})
    return None


# ENDPOINTS DE NAMESPACE
namespace_router = APIRouter(prefix="/namespaces", tags=["Namespaces"])


@namespace_router.post("/", response_model=schemas.NamespaceResponse, status_code=201)
def create_namespace(
    namespace: schemas.NamespaceCreate,
    response: Response,
    db: Session = Depends(get_db),
    current_service: models.ServiceAccount = Depends(auth.get_current_actor)
):
    logger.info("Upserting namespace", extra={"service_account": current_service.name, "namespace_nome": namespace.nome, "cluster_id": namespace.cluster_id})
    if namespace.cluster_id:
        cluster_existe = db.query(models.Cluster).filter(models.Cluster.id == namespace.cluster_id).first()
        if not cluster_existe:
            raise HTTPException(status_code=404, detail=f"Cluster id={namespace.cluster_id} não encontrado")
    if namespace.ativo_id:
        ativo_existe = db.query(models.Ativo).filter(models.Ativo.id == namespace.ativo_id).first()
        if not ativo_existe:
            raise HTTPException(status_code=404, detail=f"Ativo id={namespace.ativo_id} não encontrado")

    dados = namespace.model_dump(exclude_unset=True)
    query_existente = db.query(models.Namespace).filter(
        func.lower(models.Namespace.nome) == namespace.nome.strip().lower()
    )
    if namespace.cluster_id is not None:
        query_existente = query_existente.filter(models.Namespace.cluster_id == namespace.cluster_id)
    else:
        query_existente = query_existente.filter(models.Namespace.cluster_id.is_(None))

    existente = query_existente.first()
    if existente:
        antes = audit.model_to_dict(existente)
        for campo, valor in dados.items():
            setattr(existente, campo, valor)
        db.commit()
        db.refresh(existente)
        _audit_change(db, "namespace", existente.id, "UPDATE", antes=antes,
                      depois=audit.model_to_dict(existente), usuario=current_service.name)
        response.status_code = 200
        return existente

    db_namespace = models.Namespace(**dados)
    db.add(db_namespace)
    db.commit()
    db.refresh(db_namespace)
    _audit_change(db, "namespace", db_namespace.id, "CREATE",
                  depois=audit.model_to_dict(db_namespace), usuario=current_service.name)
    response.status_code = 201
    return db_namespace


@namespace_router.get("/", response_model=list[schemas.NamespaceResponse])
def read_namespaces(
    cluster_id: Optional[int] = None,
    db: Session = Depends(get_db),
    current_service: models.ServiceAccount = Depends(auth.get_current_actor)
):
    logger.debug("Listing namespaces", extra={"service_account": current_service.name, "cluster_id": cluster_id})
    query = db.query(models.Namespace)
    if cluster_id is not None:
        query = query.filter(models.Namespace.cluster_id == cluster_id)
    return query.all()


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


@namespace_router.put("/{namespace_id}", response_model=schemas.NamespaceResponse)
def update_namespace(
    namespace_id: int,
    namespace: schemas.NamespaceCreate,
    db: Session = Depends(get_db),
    current_service: models.ServiceAccount = Depends(auth.get_current_actor)
):
    """Atualiza um namespace (correção manual — perfil admin)."""
    _require_admin(current_service)
    db_namespace = db.query(models.Namespace).filter(models.Namespace.id == namespace_id).first()
    if not db_namespace:
        raise HTTPException(status_code=404, detail="Namespace não encontrado")

    dados = namespace.model_dump(exclude_unset=True)
    if "cluster_id" in dados and dados["cluster_id"]:
        if not db.query(models.Cluster).filter(models.Cluster.id == dados["cluster_id"]).first():
            raise HTTPException(status_code=404, detail=f"Cluster id={dados['cluster_id']} não encontrado")
    if "ativo_id" in dados and dados["ativo_id"]:
        if not db.query(models.Ativo).filter(models.Ativo.id == dados["ativo_id"]).first():
            raise HTTPException(status_code=404, detail=f"Ativo id={dados['ativo_id']} não encontrado")

    antes = audit.model_to_dict(db_namespace)
    for campo, valor in dados.items():
        setattr(db_namespace, campo, valor)
    db.commit()
    db.refresh(db_namespace)
    _audit_change(db, "namespace", db_namespace.id, "UPDATE", antes=antes,
                  depois=audit.model_to_dict(db_namespace), usuario=current_service.name)
    logger.info("Updating namespace", extra={"service_account": current_service.name, "namespace_id": namespace_id})
    return db_namespace


@namespace_router.delete("/{namespace_id}", status_code=204)
def delete_namespace(
    namespace_id: int,
    db: Session = Depends(get_db),
    current_service: models.ServiceAccount = Depends(auth.get_current_actor)
):
    """Exclui um namespace (correção manual — perfil admin)."""
    _require_admin(current_service)
    db_namespace = db.query(models.Namespace).filter(models.Namespace.id == namespace_id).first()
    if not db_namespace:
        raise HTTPException(status_code=404, detail="Namespace não encontrado")

    antes = audit.model_to_dict(db_namespace)
    db.delete(db_namespace)
    db.commit()
    _audit_change(db, "namespace", namespace_id, "DELETE", antes=antes, usuario=current_service.name)
    logger.info("Deleting namespace", extra={"service_account": current_service.name, "namespace_id": namespace_id})
    return None


# ENDPOINTS DE SERVIÇO
servico_router = APIRouter(prefix="/servicos", tags=["Serviços"])


@servico_router.post("/", response_model=schemas.ServicoResponse, status_code=201)
def create_servico(
    servico: schemas.ServicoCreate,
    response: Response,
    db: Session = Depends(get_db),
    current_service: models.ServiceAccount = Depends(auth.get_current_actor)
):
    logger.info("Upserting service", extra={"service_account": current_service.name, "servico_nome": servico.nome, "ativo_id": servico.ativo_id})
    if servico.ativo_id:
        ativo_existe = db.query(models.Ativo).filter(models.Ativo.id == servico.ativo_id).first()
        if not ativo_existe:
            raise HTTPException(status_code=404, detail=f"Ativo id={servico.ativo_id} não encontrado")

    dados = servico.model_dump(exclude_unset=True)
    query_existente = db.query(models.Servico).filter(
        func.lower(models.Servico.nome) == servico.nome.strip().lower()
    )
    if servico.ativo_id is not None:
        query_existente = query_existente.filter(models.Servico.ativo_id == servico.ativo_id)
    elif servico.host_id is not None:
        query_existente = query_existente.filter(
            models.Servico.ativo_id.is_(None),
            models.Servico.host_id == servico.host_id,
        )
    else:
        query_existente = query_existente.filter(models.Servico.ativo_id.is_(None))

    existente = query_existente.first()
    if existente:
        antes = audit.model_to_dict(existente)
        for campo, valor in dados.items():
            setattr(existente, campo, valor)
        db.commit()
        db.refresh(existente)
        _audit_change(db, "servico", existente.id, "UPDATE", antes=antes,
                      depois=audit.model_to_dict(existente), usuario=current_service.name)
        response.status_code = 200
        return existente

    db_servico = models.Servico(**dados)
    db.add(db_servico)
    db.commit()
    db.refresh(db_servico)
    _audit_change(db, "servico", db_servico.id, "CREATE",
                  depois=audit.model_to_dict(db_servico), usuario=current_service.name)
    response.status_code = 201
    return db_servico


@servico_router.get("/", response_model=list[schemas.ServicoResponse])
def read_servicos(
    ativo_id: Optional[int] = None,
    db: Session = Depends(get_db),
    current_service: models.ServiceAccount = Depends(auth.get_current_actor)
):
    logger.debug("Listing services", extra={"service_account": current_service.name, "ativo_id": ativo_id})
    query = db.query(models.Servico)
    if ativo_id is not None:
        query = query.filter(models.Servico.ativo_id == ativo_id)
    return query.all()


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


@servico_router.put("/{servico_id}", response_model=schemas.ServicoResponse)
def update_servico(
    servico_id: int,
    servico: schemas.ServicoCreate,
    db: Session = Depends(get_db),
    current_service: models.ServiceAccount = Depends(auth.get_current_actor)
):
    """Atualiza um serviço (correção manual — perfil admin)."""
    _require_admin(current_service)
    db_servico = db.query(models.Servico).filter(models.Servico.id == servico_id).first()
    if not db_servico:
        raise HTTPException(status_code=404, detail="Serviço não encontrado")

    dados = servico.model_dump(exclude_unset=True)
    if "ativo_id" in dados and dados["ativo_id"]:
        if not db.query(models.Ativo).filter(models.Ativo.id == dados["ativo_id"]).first():
            raise HTTPException(status_code=404, detail=f"Ativo id={dados['ativo_id']} não encontrado")

    antes = audit.model_to_dict(db_servico)
    for campo, valor in dados.items():
        setattr(db_servico, campo, valor)
    db.commit()
    db.refresh(db_servico)
    _audit_change(db, "servico", db_servico.id, "UPDATE", antes=antes,
                  depois=audit.model_to_dict(db_servico), usuario=current_service.name)
    logger.info("Updating service", extra={"service_account": current_service.name, "servico_id": servico_id})
    return db_servico


@servico_router.delete("/{servico_id}", status_code=204)
def delete_servico(
    servico_id: int,
    db: Session = Depends(get_db),
    current_service: models.ServiceAccount = Depends(auth.get_current_actor)
):
    """Exclui um serviço (correção manual — perfil admin)."""
    _require_admin(current_service)
    db_servico = db.query(models.Servico).filter(models.Servico.id == servico_id).first()
    if not db_servico:
        raise HTTPException(status_code=404, detail="Serviço não encontrado")

    antes = audit.model_to_dict(db_servico)
    db.delete(db_servico)
    db.commit()
    _audit_change(db, "servico", servico_id, "DELETE", antes=antes, usuario=current_service.name)
    logger.info("Deleting service", extra={"service_account": current_service.name, "servico_id": servico_id})
    return None


# ENDPOINTS DE SERVIÇO NEGÓCIO
servico_negocio_router = APIRouter(prefix="/servicos-negocio", tags=["Serviços de Negócio"])


@servico_negocio_router.post("/", response_model=schemas.ServicoNegocioResponse, status_code=201)
def create_servico_negocio(
    servico: schemas.ServicoNegocioCreate,
    response: Response,
    db: Session = Depends(get_db),
    current_service: models.ServiceAccount = Depends(auth.get_current_actor)
):
    logger.info("Upserting business service", extra={"service_account": current_service.name, "name": servico.nome})
    if servico.ativo_id:
        ativo_existe = db.query(models.Ativo).filter(models.Ativo.id == servico.ativo_id).first()
        if not ativo_existe:
            raise HTTPException(status_code=404, detail=f"Ativo id={servico.ativo_id} não encontrado")

    dados = servico.model_dump(exclude_unset=True)
    existente = db.query(models.ServicoNegocio).filter(
        func.lower(models.ServicoNegocio.nome) == servico.nome.strip().lower()
    ).first()
    if existente:
        antes = audit.model_to_dict(existente)
        for campo, valor in dados.items():
            setattr(existente, campo, valor)
        db.commit()
        db.refresh(existente)
        _audit_change(db, "servico_negocio", existente.id, "UPDATE", antes=antes,
                      depois=audit.model_to_dict(existente), usuario=current_service.name)
        response.status_code = 200
        return existente

    db_servico = models.ServicoNegocio(**dados)
    db.add(db_servico)
    db.commit()
    db.refresh(db_servico)
    _audit_change(db, "servico_negocio", db_servico.id, "CREATE",
                  depois=audit.model_to_dict(db_servico), usuario=current_service.name)
    response.status_code = 201
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


@servico_negocio_router.put("/{servico_id}", response_model=schemas.ServicoNegocioResponse)
def update_servico_negocio(
    servico_id: int,
    servico: schemas.ServicoNegocioCreate,
    db: Session = Depends(get_db),
    current_service: models.ServiceAccount = Depends(auth.get_current_actor)
):
    """Atualiza um serviço de negócio (correção manual — perfil admin)."""
    _require_admin(current_service)
    db_servico = db.query(models.ServicoNegocio).filter(models.ServicoNegocio.id == servico_id).first()
    if not db_servico:
        raise HTTPException(status_code=404, detail="Serviço de negócio não encontrado")

    dados = servico.model_dump(exclude_unset=True)
    if "ativo_id" in dados and dados["ativo_id"]:
        if not db.query(models.Ativo).filter(models.Ativo.id == dados["ativo_id"]).first():
            raise HTTPException(status_code=404, detail=f"Ativo id={dados['ativo_id']} não encontrado")

    antes = audit.model_to_dict(db_servico)
    for campo, valor in dados.items():
        setattr(db_servico, campo, valor)
    db.commit()
    db.refresh(db_servico)
    _audit_change(db, "servico_negocio", db_servico.id, "UPDATE", antes=antes,
                  depois=audit.model_to_dict(db_servico), usuario=current_service.name)
    logger.info("Updating business service", extra={"service_account": current_service.name, "servico_id": servico_id})
    return db_servico


@servico_negocio_router.delete("/{servico_id}", status_code=204)
def delete_servico_negocio(
    servico_id: int,
    db: Session = Depends(get_db),
    current_service: models.ServiceAccount = Depends(auth.get_current_actor)
):
    """Exclui um serviço de negócio (correção manual — perfil admin)."""
    _require_admin(current_service)
    db_servico = db.query(models.ServicoNegocio).filter(models.ServicoNegocio.id == servico_id).first()
    if not db_servico:
        raise HTTPException(status_code=404, detail="Serviço de negócio não encontrado")

    antes = audit.model_to_dict(db_servico)
    db.delete(db_servico)
    db.commit()
    _audit_change(db, "servico_negocio", servico_id, "DELETE", antes=antes, usuario=current_service.name)
    logger.info("Deleting business service", extra={"service_account": current_service.name, "servico_id": servico_id})
    return None


# ENDPOINTS DE INSTÂNCIA APLICAÇÃO
instancia_router = APIRouter(prefix="/instancias-aplicacao", tags=["Instâncias de Aplicação"])


@instancia_router.post("/", response_model=schemas.InstanciaAplicacaoResponse, status_code=201)
def create_instancia_aplicacao(
    instancia: schemas.InstanciaAplicacaoCreate,
    response: Response,
    db: Session = Depends(get_db),
    current_service: models.ServiceAccount = Depends(auth.get_current_actor)
):
    logger.info("Upserting application instance", extra={"service_account": current_service.name, "aplicacao_id": instancia.aplicacao_id, "ativo_id": instancia.ativo_id})
    aplicacao = db.query(models.Aplicacao).filter(models.Aplicacao.id == instancia.aplicacao_id).first()
    if not aplicacao:
        raise HTTPException(status_code=404, detail=f"Aplicação id={instancia.aplicacao_id} não encontrada")
    if instancia.ativo_id:
        ativo_existe = db.query(models.Ativo).filter(models.Ativo.id == instancia.ativo_id).first()
        if not ativo_existe:
            raise HTTPException(status_code=404, detail=f"Ativo id={instancia.ativo_id} não encontrado")

    dados = instancia.model_dump(exclude_unset=True)
    query_existente = db.query(models.InstanciaAplicacao).filter(
        models.InstanciaAplicacao.aplicacao_id == instancia.aplicacao_id
    )
    if instancia.ativo_id is not None:
        query_existente = query_existente.filter(models.InstanciaAplicacao.ativo_id == instancia.ativo_id)
    else:
        query_existente = query_existente.filter(models.InstanciaAplicacao.ativo_id.is_(None))

    if instancia.porta is not None:
        query_existente = query_existente.filter(models.InstanciaAplicacao.porta == instancia.porta)
    else:
        query_existente = query_existente.filter(models.InstanciaAplicacao.porta.is_(None))

    existente = query_existente.first()
    if existente:
        antes = audit.model_to_dict(existente)
        for campo, valor in dados.items():
            setattr(existente, campo, valor)
        db.commit()
        db.refresh(existente)
        _audit_change(db, "instancia_aplicacao", existente.id, "UPDATE", antes=antes,
                      depois=audit.model_to_dict(existente), usuario=current_service.name)
        response.status_code = 200
        return existente

    db_instancia = models.InstanciaAplicacao(**dados)
    db.add(db_instancia)
    db.commit()
    db.refresh(db_instancia)
    _audit_change(db, "instancia_aplicacao", db_instancia.id, "CREATE",
                  depois=audit.model_to_dict(db_instancia), usuario=current_service.name)
    response.status_code = 201
    return db_instancia


@instancia_router.get("/", response_model=list[schemas.InstanciaAplicacaoResponse])
def read_instancias_aplicacao(
    aplicacao_id: Optional[int] = None,
    ativo_id: Optional[int] = None,
    db: Session = Depends(get_db),
    current_service: models.ServiceAccount = Depends(auth.get_current_actor)
):
    logger.debug("Listing application instances", extra={"service_account": current_service.name, "aplicacao_id": aplicacao_id, "ativo_id": ativo_id})
    query = db.query(models.InstanciaAplicacao)
    if aplicacao_id:
        query = query.filter(models.InstanciaAplicacao.aplicacao_id == aplicacao_id)
    if ativo_id:
        query = query.filter(models.InstanciaAplicacao.ativo_id == ativo_id)
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


@instancia_router.put("/{instancia_id}", response_model=schemas.InstanciaAplicacaoResponse)
def update_instancia_aplicacao(
    instancia_id: int,
    instancia: schemas.InstanciaAplicacaoCreate,
    db: Session = Depends(get_db),
    current_service: models.ServiceAccount = Depends(auth.get_current_actor)
):
    """Atualiza uma instância de aplicação (correção manual — perfil admin)."""
    _require_admin(current_service)
    db_instancia = db.query(models.InstanciaAplicacao).filter(models.InstanciaAplicacao.id == instancia_id).first()
    if not db_instancia:
        raise HTTPException(status_code=404, detail="Instância de aplicação não encontrada")

    dados = instancia.model_dump(exclude_unset=True)
    if "aplicacao_id" in dados:
        if not db.query(models.Aplicacao).filter(models.Aplicacao.id == dados["aplicacao_id"]).first():
            raise HTTPException(status_code=404, detail=f"Aplicação id={dados['aplicacao_id']} não encontrada")
    if "ativo_id" in dados and dados["ativo_id"]:
        if not db.query(models.Ativo).filter(models.Ativo.id == dados["ativo_id"]).first():
            raise HTTPException(status_code=404, detail=f"Ativo id={dados['ativo_id']} não encontrado")

    antes = audit.model_to_dict(db_instancia)
    for campo, valor in dados.items():
        setattr(db_instancia, campo, valor)
    db.commit()
    db.refresh(db_instancia)
    _audit_change(db, "instancia_aplicacao", db_instancia.id, "UPDATE", antes=antes,
                  depois=audit.model_to_dict(db_instancia), usuario=current_service.name)
    logger.info("Updating application instance", extra={"service_account": current_service.name, "instancia_id": instancia_id})
    return db_instancia


@instancia_router.delete("/{instancia_id}", status_code=204)
def delete_instancia_aplicacao(
    instancia_id: int,
    db: Session = Depends(get_db),
    current_service: models.ServiceAccount = Depends(auth.get_current_actor)
):
    """Exclui uma instância de aplicação (correção manual — perfil admin)."""
    _require_admin(current_service)
    db_instancia = db.query(models.InstanciaAplicacao).filter(models.InstanciaAplicacao.id == instancia_id).first()
    if not db_instancia:
        raise HTTPException(status_code=404, detail="Instância de aplicação não encontrada")

    antes = audit.model_to_dict(db_instancia)
    db.delete(db_instancia)
    db.commit()
    _audit_change(db, "instancia_aplicacao", instancia_id, "DELETE", antes=antes, usuario=current_service.name)
    logger.info("Deleting application instance", extra={"service_account": current_service.name, "instancia_id": instancia_id})
    return None