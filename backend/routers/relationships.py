from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session, joinedload
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
    except Exception:
        logger.warning("Falha ao gravar audit log", exc_info=True)

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


@router.put("/{tipo_id}", response_model=schemas.TipoRelacionamentoResponse)
def update_tipo_relacionamento(
    tipo_id: int,
    tipo: schemas.TipoRelacionamentoCreate,
    db: Session = Depends(get_db),
    current_service: models.ServiceAccount = Depends(auth.get_current_actor)
):
    """Atualiza um tipo de relacionamento (correção manual — perfil admin)."""
    _require_admin(current_service)
    db_tipo = db.query(models.TipoRelacionamento).filter(models.TipoRelacionamento.id == tipo_id).first()
    if not db_tipo:
        raise HTTPException(status_code=404, detail="Tipo de relacionamento não encontrado")

    dados = tipo.model_dump(exclude_unset=True)
    antes = audit.model_to_dict(db_tipo)
    for campo, valor in dados.items():
        setattr(db_tipo, campo, valor)
    db.commit()
    db.refresh(db_tipo)
    _audit_change(db, "tipo_relacionamento", db_tipo.id, "UPDATE", antes=antes,
                  depois=audit.model_to_dict(db_tipo), usuario=current_service.name)
    logger.info("Updating relationship type", extra={"service_account": current_service.name, "tipo_id": tipo_id})
    return db_tipo


@router.delete("/{tipo_id}", status_code=204)
def delete_tipo_relacionamento(
    tipo_id: int,
    db: Session = Depends(get_db),
    current_service: models.ServiceAccount = Depends(auth.get_current_actor)
):
    """Exclui um tipo de relacionamento (correção manual — perfil admin)."""
    _require_admin(current_service)
    db_tipo = db.query(models.TipoRelacionamento).filter(models.TipoRelacionamento.id == tipo_id).first()
    if not db_tipo:
        raise HTTPException(status_code=404, detail="Tipo de relacionamento não encontrado")

    em_uso = db.query(models.Relacionamento).filter(models.Relacionamento.tipo_id == tipo_id).count()
    if em_uso > 0:
        raise HTTPException(
            status_code=409,
            detail=f"Tipo em uso por {em_uso} relacionamento(s). Retifique-os antes de excluir.")

    antes = audit.model_to_dict(db_tipo)
    db.delete(db_tipo)
    db.commit()
    _audit_change(db, "tipo_relacionamento", tipo_id, "DELETE", antes=antes, usuario=current_service.name)
    logger.info("Deleting relationship type", extra={"service_account": current_service.name, "tipo_id": tipo_id})
    return None


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


@rel_router.put("/{rel_id}", response_model=schemas.RelacionamentoResponse)
def update_relacionamento(
    rel_id: int,
    rel: schemas.RelacionamentoCreate,
    db: Session = Depends(get_db),
    current_service: models.ServiceAccount = Depends(auth.get_current_actor)
):
    """Atualiza um relacionamento (correção manual — perfil admin)."""
    _require_admin(current_service)
    db_rel = db.query(models.Relacionamento).filter(models.Relacionamento.id == rel_id).first()
    if not db_rel:
        raise HTTPException(status_code=404, detail="Relacionamento não encontrado")

    dados = rel.model_dump(exclude_unset=True)
    if "origem_id" in dados and not db.query(models.Ativo).filter(models.Ativo.id == dados["origem_id"]).first():
        raise HTTPException(status_code=404, detail=f"Ativo origem id={dados['origem_id']} não encontrado")
    if "destino_id" in dados and not db.query(models.Ativo).filter(models.Ativo.id == dados["destino_id"]).first():
        raise HTTPException(status_code=404, detail=f"Ativo destino id={dados['destino_id']} não encontrado")
    if "tipo_id" in dados and not db.query(models.TipoRelacionamento).filter(models.TipoRelacionamento.id == dados["tipo_id"]).first():
        raise HTTPException(status_code=404, detail=f"Tipo relacionamento id={dados['tipo_id']} não encontrado")

    antes = audit.model_to_dict(db_rel)
    for campo, valor in dados.items():
        setattr(db_rel, campo, valor)
    db.commit()
    db.refresh(db_rel)
    _audit_change(db, "relacionamento", db_rel.id, "UPDATE", antes=antes,
                  depois=audit.model_to_dict(db_rel), usuario=current_service.name)
    logger.info("Updating relationship", extra={"service_account": current_service.name, "rel_id": rel_id})
    return db_rel


@rel_router.delete("/{rel_id}", status_code=204)
def delete_relacionamento(
    rel_id: int,
    db: Session = Depends(get_db),
    current_service: models.ServiceAccount = Depends(auth.get_current_actor)
):
    """Exclui um relacionamento (correção manual — perfil admin)."""
    _require_admin(current_service)
    db_rel = db.query(models.Relacionamento).filter(models.Relacionamento.id == rel_id).first()
    if not db_rel:
        raise HTTPException(status_code=404, detail="Relacionamento não encontrado")

    antes = audit.model_to_dict(db_rel)
    db.delete(db_rel)
    db.commit()
    _audit_change(db, "relacionamento", rel_id, "DELETE", antes=antes, usuario=current_service.name)
    logger.info("Deleting relationship", extra={"service_account": current_service.name, "rel_id": rel_id})
    return None