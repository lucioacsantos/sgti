from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session, joinedload
from typing import Optional
import models, schemas, auth
from database import get_db
import logging

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/tipos-relacionamento", tags=["Tipos de Relacionamento"])


@router.post("/", response_model=schemas.TipoRelacionamentoResponse, status_code=201)
def create_tipo_relacionamento(
    tipo: schemas.TipoRelacionamentoCreate,
    db: Session = Depends(get_db),
    current_service: models.ServiceAccount = Depends(auth.get_current_actor)
):
    logger.info("Creating relationship type", extra={"service_account": current_service.name, "tipo_nome": tipo.nome})
    db_tipo = models.TipoRelacionamento(**tipo.model_dump(exclude_unset=True))
    db.add(db_tipo)
    db.commit()
    db.refresh(db_tipo)
    return db_tipo


@router.get("/", response_model=list[schemas.TipoRelacionamentoResponse])
def read_tipos_relacionamento(
    db: Session = Depends(get_db),
    current_service: models.ServiceAccount = Depends(auth.get_current_actor)
):
    logger.debug("Listing relationship types", extra={"service_account": current_service.name})
    return db.query(models.TipoRelacionamento).all()


@router.get("/{tipo_id}", response_model=schemas.TipoRelacionamentoResponse)
def read_tipo_relacionamento(
    tipo_id: int,
    db: Session = Depends(get_db),
    current_service: models.ServiceAccount = Depends(auth.get_current_actor)
):
    logger.debug("Reading relationship type", extra={"service_account": current_service.name, "tipo_id": tipo_id})
    tipo = db.query(models.TipoRelacionamento).filter(models.TipoRelacionamento.id == tipo_id).first()
    if not tipo:
        raise HTTPException(status_code=404, detail="Tipo de relacionamento não encontrado")
    return tipo


# ENDPOINTS DE RELACIONAMENTO
rel_router = APIRouter(prefix="/relacionamentos", tags=["Relacionamentos"])


@rel_router.post("/", response_model=schemas.RelacionamentoResponse, status_code=201)
def create_relacionamento(
    rel: schemas.RelacionamentoCreate,
    db: Session = Depends(get_db),
    current_service: models.ServiceAccount = Depends(auth.get_current_actor)
):
    logger.info("Creating relationship", extra={"service_account": current_service.name, "origem_id": rel.origem_id, "destino_id": rel.destino_id})
    origem = db.query(models.Ativo).filter(models.Ativo.id == rel.origem_id).first()
    if not origem:
        raise HTTPException(status_code=404, detail=f"Ativo origem id={rel.origem_id} não encontrado")
    destino = db.query(models.Ativo).filter(models.Ativo.id == rel.destino_id).first()
    if not destino:
        raise HTTPException(status_code=404, detail=f"Ativo destino id={rel.destino_id} não encontrado")
    tipo = db.query(models.TipoRelacionamento).filter(models.TipoRelacionamento.id == rel.tipo_id).first()
    if not tipo:
        raise HTTPException(status_code=404, detail=f"Tipo relacionamento id={rel.tipo_id} não encontrado")
    db_rel = models.Relacionamento(**rel.model_dump(exclude_unset=True))
    db.add(db_rel)
    db.commit()
    db.refresh(db_rel)
    return db_rel


@rel_router.get("/", response_model=list[schemas.RelacionamentoResponse])
def read_relacionamentos(
    origem_id: Optional[int] = None,
    destino_id: Optional[int] = None,
    skip: int = 0,
    limit: int = 50,
    db: Session = Depends(get_db),
    current_service: models.ServiceAccount = Depends(auth.get_current_actor)
):
    logger.debug("Listing relationships", extra={"service_account": current_service.name, "origem_id": origem_id, "destino_id": destino_id})
    query = db.query(models.Relacionamento).options(
        joinedload(models.Relacionamento.origem),
        joinedload(models.Relacionamento.destino),
        joinedload(models.Relacionamento.tipo)
    )
    if origem_id:
        query = query.filter(models.Relacionamento.origem_id == origem_id)
    if destino_id:
        query = query.filter(models.Relacionamento.destino_id == destino_id)
    return query.offset(skip).limit(min(limit, 100)).all()


@rel_router.get("/{rel_id}", response_model=schemas.RelacionamentoResponse)
def read_relacionamento(
    rel_id: int,
    db: Session = Depends(get_db),
    current_service: models.ServiceAccount = Depends(auth.get_current_actor)
):
    logger.debug("Reading relationship", extra={"service_account": current_service.name, "rel_id": rel_id})
    rel = db.query(models.Relacionamento).options(
        joinedload(models.Relacionamento.origem),
        joinedload(models.Relacionamento.destino),
        joinedload(models.Relacionamento.tipo)
    ).filter(models.Relacionamento.id == rel_id).first()
    if not rel:
        raise HTTPException(status_code=404, detail="Relacionamento não encontrado")
    return rel