from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlalchemy.orm import Session, joinedload
from sqlalchemy import func
from typing import Optional
import models, schemas, auth, audit
from database import get_db
import logging

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/ativos", tags=["Ativos"])


@router.post("/", response_model=schemas.AtivoResponse, status_code=201)
def create_ativo(
    ativo: schemas.AtivoCreate,
    db: Session = Depends(get_db),
    current_service: models.ServiceAccount = Depends(auth.get_service_account)
):
    logger.info("Creating asset", extra={"service_account": current_service.name, "asset_name": ativo.nome})

    # Check for duplicate (case-insensitive)
    existente = db.query(models.Ativo).filter(
        func.lower(models.Ativo.nome) == ativo.nome.lower()
    ).first()

    if existente:
        raise HTTPException(
            status_code=409,
            detail=f"Ativo com nome '{ativo.nome}' já existe (id={existente.id})"
        )

    db_ativo = models.Ativo(**ativo.model_dump(exclude_unset=True))
    db.add(db_ativo)
    db.commit()
    db.refresh(db_ativo)

    # Audit log
    audit.create_audit_log(
        db=db,
        entidade="ativo",
        entidade_id=db_ativo.id,
        acao="CREATE",
        depois=audit.model_to_dict(db_ativo),
        usuario=current_service.name,
    )
    db.commit()

    return db_ativo


@router.get("/", response_model=list[schemas.AtivoResponse])
def read_ativos(
    skip: int = 0,
    limit: int = 50,
    db: Session = Depends(get_db),
    current_service: models.ServiceAccount = Depends(auth.get_service_account)
):
    logger.debug("Listing assets", extra={"service_account": current_service.name, "skip": skip, "limit": limit})
    ativos = db.query(models.Ativo).offset(skip).limit(min(limit, 100)).all()
    return ativos


@router.put("/{nome}", response_model=schemas.AtivoResponse)
def upsert_ativo(
    nome: str,
    ativo: schemas.AtivoUpdate,
    response: Response,
    db: Session = Depends(get_db),
    current_service: models.ServiceAccount = Depends(auth.get_service_account)
):
    logger.info("Upserting asset", extra={"service_account": current_service.name, "asset_name": nome})

    db_ativo = db.query(models.Ativo).filter(
        func.lower(models.Ativo.nome) == nome.lower()
    ).first()

    dados = ativo.model_dump(exclude_unset=True)

    if db_ativo:
        antes = audit.model_to_dict(db_ativo)
        for campo, valor in dados.items():
            setattr(db_ativo, campo, valor)
        db.commit()
        db.refresh(db_ativo)
        
        audit.create_audit_log(
            db=db,
            entidade="ativo",
            entidade_id=db_ativo.id,
            acao="UPDATE",
            antes=antes,
            depois=audit.model_to_dict(db_ativo),
            usuario=current_service.name,
        )
        db.commit()
        
        response.status_code = 200
        return db_ativo

    dados.setdefault("nome", nome)

    try:
        novo = models.Ativo(**dados)
        db.add(novo)
        db.commit()
        db.refresh(novo)
        
        audit.create_audit_log(
            db=db,
            entidade="ativo",
            entidade_id=novo.id,
            acao="CREATE",
            depois=audit.model_to_dict(novo),
            usuario=current_service.name,
        )
        db.commit()
        
        response.status_code = 201
        return novo
    except Exception:
        db.rollback()
        # Race condition: outro processo criou entre a consulta e a inserção
        db_ativo = db.query(models.Ativo).filter(
            func.lower(models.Ativo.nome) == nome.lower()
        ).first()
        if db_ativo:
            antes = audit.model_to_dict(db_ativo)
            for campo, valor in dados.items():
                setattr(db_ativo, campo, valor)
            db.commit()
            db.refresh(db_ativo)
            
            audit.create_audit_log(
                db=db,
                entidade="ativo",
                entidade_id=db_ativo.id,
                acao="UPDATE",
                antes=antes,
                depois=audit.model_to_dict(db_ativo),
                usuario=current_service.name,
            )
            db.commit()
            
            response.status_code = 200
            return db_ativo
        raise


@router.get("/{nome}", response_model=schemas.AtivoResponse)
def read_ativo(nome: str, db: Session = Depends(get_db)):
    db_ativo = db.query(models.Ativo).filter(
        func.lower(models.Ativo.nome) == nome.lower()
    ).first()
    if db_ativo is None:
        raise HTTPException(status_code=404, detail="Ativo não encontrado")
    return db_ativo


@router.delete("/{nome}", status_code=204)
def delete_ativo(
    nome: str,
    db: Session = Depends(get_db),
    current_service: models.ServiceAccount = Depends(auth.get_service_account)
):
    logger.info("Deleting asset", extra={"service_account": current_service.name, "asset_name": nome})
    db_ativo = db.query(models.Ativo).filter(
        func.lower(models.Ativo.nome) == nome.lower()
    ).first()
    if not db_ativo:
        raise HTTPException(status_code=404, detail="Ativo não encontrado")
    
    antes = audit.model_to_dict(db_ativo)
    db.delete(db_ativo)
    db.commit()
    
    audit.create_audit_log(
        db=db,
        entidade="ativo",
        entidade_id=None,
        acao="DELETE",
        antes=antes,
        usuario=current_service.name,
    )
    db.commit()