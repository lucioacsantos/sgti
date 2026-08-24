from fastapi import APIRouter, Depends, HTTPException, Response
from sqlalchemy.orm import Session
from typing import Optional
import models, schemas, auth, audit
from database import get_db
from sqlalchemy.dialects.postgresql import insert as pg_insert
import logging

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/enderecos-ip", tags=["Endereços IP"])


@router.post("/", response_model=schemas.EnderecoIpResponse, status_code=201)
def upsert_endereco_ip(
    payload: schemas.EnderecoIpUpsert,
    response: Response,
    db: Session = Depends(get_db),
    current_service: models.ServiceAccount = Depends(auth.get_service_account)
):
    logger.info("Upserting IP address", extra={"service_account": current_service.name, "asset_id": payload.ativo_id, "ip": payload.ip})

    # Verifica se o ativo existe (evita erro de FK confuso)
    ativo_existe = db.query(models.Ativo).filter(models.Ativo.id == payload.ativo_id).first()
    if not ativo_existe:
        raise HTTPException(status_code=404, detail=f"Ativo id={payload.ativo_id} não encontrado")

    dados = payload.model_dump(exclude_unset=True)

    # Se marcado como primário, desmarca os demais IPs do mesmo ativo
    if dados.get("primario"):
        db.query(models.EnderecoIp).filter(
            models.EnderecoIp.ativo_id == payload.ativo_id,
            models.EnderecoIp.primario == True
        ).update({"primario": False})

    # Use PostgreSQL ON CONFLICT for atomic upsert
    stmt = pg_insert(models.EnderecoIp).values(**dados)
    stmt = stmt.on_conflict_do_update(
        index_elements=["ativo_id", "ip"],
        set_={col: stmt.excluded[col] for col in ["tipo", "interface", "descricao", "primario", "ativo"]}
    ).returning(models.EnderecoIp)
    
    result = db.execute(stmt)
    db_ip = result.scalar_one()
    
    # Determine if created or updated
    is_new = db_ip.created_at == db_ip.updated_at
    
    if is_new:
        audit.create_audit_log(
            db=db,
            entidade="endereco_ip",
            entidade_id=db_ip.id,
            acao="CREATE",
            depois=audit.model_to_dict(db_ip),
            usuario=current_service.name,
        )
        response.status_code = 201
    else:
        audit.create_audit_log(
            db=db,
            entidade="endereco_ip",
            entidade_id=db_ip.id,
            acao="UPDATE",
            depois=audit.model_to_dict(db_ip),
            usuario=current_service.name,
        )
        response.status_code = 200
    
    db.commit()
    db.refresh(db_ip)
    return db_ip


@router.get("/", response_model=list[schemas.EnderecoIpResponse])
def read_enderecos_ip(
    ativo_id: Optional[int] = None,
    skip: int = 0,
    limit: int = 50,
    db: Session = Depends(get_db),
    current_service: models.ServiceAccount = Depends(auth.get_service_account)
):
    query = db.query(models.EnderecoIp)
    if ativo_id:
        query = query.filter(models.EnderecoIp.ativo_id == ativo_id)
    return query.offset(skip).limit(min(limit, 100)).all()


@router.delete("/{ip_id}", status_code=204)
def delete_endereco_ip(
    ip_id: int,
    db: Session = Depends(get_db),
    current_service: models.ServiceAccount = Depends(auth.get_service_account)
):
    logger.info("Deleting IP address", extra={"service_account": current_service.name, "ip_id": ip_id})
    db_ip = db.query(models.EnderecoIp).filter(models.EnderecoIp.id == ip_id).first()
    if not db_ip:
        raise HTTPException(status_code=404, detail="Endereço IP não encontrado")
    
    antes = audit.model_to_dict(db_ip)
    db.delete(db_ip)
    db.commit()
    
    audit.create_audit_log(
        db=db,
        entidade="endereco_ip",
        entidade_id=ip_id,
        acao="DELETE",
        antes=antes,
        usuario=current_service.name,
    )
    db.commit()