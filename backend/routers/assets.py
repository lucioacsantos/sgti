# Objetivo: CRUD de ativos de TI (/ativos) com busca, filtros, upsert por nome/bios_uuid/fqdn e auditoria.
# Author: Lucio A C Santos — GitHub: https://github.com/lucioacsantos

from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlalchemy.orm import Session, joinedload
from sqlalchemy import func, or_
from typing import Optional
import models, schemas, auth, audit
from database import get_db
import logging

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/ativos", tags=["Ativos"])


def _buscar_ativo_correlacionado(
    db: Session,
    nome: str,
    bios_uuid: Optional[str] = None,
    fqdn: Optional[str] = None,
) -> Optional[models.Ativo]:
    """Localiza ativo existente priorizando bios_uuid, depois nome exato e fallback por FQDN."""
    if bios_uuid:
        por_uuid = db.query(models.Ativo).filter(
            func.lower(models.Ativo.bios_uuid) == bios_uuid.strip().lower()
        ).first()
        if por_uuid:
            return por_uuid

    por_nome = db.query(models.Ativo).filter(
        func.lower(models.Ativo.nome) == nome.strip().lower()
    ).first()
    if por_nome:
        return por_nome

    if fqdn:
        por_fqdn = db.query(models.Ativo).filter(
            or_(
                func.lower(models.Ativo.fqdn) == fqdn.strip().lower(),
                func.lower(models.Ativo.nome) == fqdn.strip().lower(),
            )
        ).first()
        if por_fqdn:
            return por_fqdn

    # Se nome recebido da fonte (ex.: Satellite) é um FQDN, tenta casar com o hostname curto
    if "." in nome:
        curto = nome.split(".")[0].strip()
        if curto:
            por_curto = db.query(models.Ativo).filter(
                or_(
                    func.lower(models.Ativo.nome) == curto.lower(),
                    func.lower(models.Ativo.fqdn) == nome.strip().lower(),
                )
            ).first()
            if por_curto:
                return por_curto

    return None


@router.post("/", response_model=schemas.AtivoResponse, status_code=201)
def create_ativo(
    ativo: schemas.AtivoCreate,
    db: Session = Depends(get_db),
    current_service: models.ServiceAccount = Depends(auth.get_current_actor)
):
    logger.info("Creating asset", extra={"service_account": current_service.name, "asset_name": ativo.nome})

    # Check for duplicate (case-insensitive name or bios_uuid)
    existente = db.query(models.Ativo).filter(
        func.lower(models.Ativo.nome) == ativo.nome.lower()
    ).first()

    if existente:
        raise HTTPException(
            status_code=409,
            detail=f"Ativo com nome '{ativo.nome}' já existe (id={existente.id})"
        )

    if ativo.bios_uuid:
        existente_uuid = db.query(models.Ativo).filter(
            func.lower(models.Ativo.bios_uuid) == ativo.bios_uuid.strip().lower()
        ).first()
        if existente_uuid:
            raise HTTPException(
                status_code=409,
                detail=f"Ativo com bios_uuid '{ativo.bios_uuid}' já existe (id={existente_uuid.id})"
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
    search: Optional[str] = None,
    tipo_id: Optional[int] = None,
    ambiente_id: Optional[int] = None,
    areas_id: Optional[int] = None,
    bios_uuid: Optional[str] = None,
    fqdn: Optional[str] = None,
    db: Session = Depends(get_db),
    current_service: models.ServiceAccount = Depends(auth.get_current_actor)
):
    logger.debug(
        "Listing assets",
        extra={
            "service_account": current_service.name,
            "skip": skip,
            "limit": limit,
            "search": search,
            "tipo_id": tipo_id,
            "ambiente_id": ambiente_id,
            "areas_id": areas_id,
            "bios_uuid": bios_uuid,
            "fqdn": fqdn,
        },
    )
    query = db.query(models.Ativo)

    if search:
        termo = f"%{search.lower()}%"
        query = query.filter(or_(
            func.lower(models.Ativo.nome).like(termo),
            func.lower(models.Ativo.descricao).like(termo),
            func.lower(models.Ativo.fqdn).like(termo),
            func.lower(models.Ativo.bios_uuid).like(termo),
        ))
    if tipo_id:
        query = query.filter(models.Ativo.tipo_id == tipo_id)
    if ambiente_id:
        query = query.filter(models.Ativo.ambiente_id == ambiente_id)
    if areas_id:
        query = query.filter(models.Ativo.areas_id == areas_id)
    if bios_uuid:
        query = query.filter(func.lower(models.Ativo.bios_uuid) == bios_uuid.strip().lower())
    if fqdn:
        query = query.filter(func.lower(models.Ativo.fqdn) == fqdn.strip().lower())

    query = query.order_by(func.lower(models.Ativo.nome))

    ativos = query.offset(skip).limit(min(limit, 5000)).all()
    return ativos


@router.put("/{nome}", response_model=schemas.AtivoResponse)
def upsert_ativo(
    nome: str,
    ativo: schemas.AtivoUpdate,
    response: Response,
    db: Session = Depends(get_db),
    current_service: models.ServiceAccount = Depends(auth.get_current_actor)
):
    logger.info("Upserting asset", extra={"service_account": current_service.name, "asset_name": nome})

    dados = ativo.model_dump(exclude_unset=True)
    db_ativo = _buscar_ativo_correlacionado(
        db,
        nome=nome,
        bios_uuid=dados.get("bios_uuid"),
        fqdn=dados.get("fqdn"),
    )

    manual = auth.is_manual_user(current_service)
    acao_update = "UPDATE_MANUAL" if manual else "UPDATE"

    if db_ativo:
        antes = audit.model_to_dict(db_ativo)
        for campo, valor in dados.items():
            setattr(db_ativo, campo, valor)
        # Se a chamada trouxe um FQDN no parâmetro de rota (ex.: Satellite) e o ativo
        # ainda não tinha fqdn preenchido, registra o fqdn mantendo o nome canônico
        if "." in nome and not db_ativo.fqdn and "fqdn" not in dados:
            db_ativo.fqdn = nome
        db.commit()
        db.refresh(db_ativo)

        audit.create_audit_log(
            db=db,
            entidade="ativo",
            entidade_id=db_ativo.id,
            acao=acao_update,
            antes=antes,
            depois=audit.model_to_dict(db_ativo),
            usuario=current_service.name,
        )
        db.commit()

        response.status_code = 200
        return db_ativo

    dados.setdefault("nome", nome)
    if "." in nome and "fqdn" not in dados:
        dados["fqdn"] = nome

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
        db_ativo = _buscar_ativo_correlacionado(
            db,
            nome=nome,
            bios_uuid=dados.get("bios_uuid"),
            fqdn=dados.get("fqdn"),
        )
        if db_ativo:
            antes = audit.model_to_dict(db_ativo)
            for campo, valor in dados.items():
                if campo != "nome" or dados.get("nome"):
                    setattr(db_ativo, campo, valor)
            db.commit()
            db.refresh(db_ativo)

            audit.create_audit_log(
                db=db,
                entidade="ativo",
                entidade_id=db_ativo.id,
                acao=acao_update,
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
    db_ativo = _buscar_ativo_correlacionado(db, nome=nome)
    if db_ativo is None:
        raise HTTPException(status_code=404, detail="Ativo não encontrado")
    return db_ativo


@router.delete("/{nome}", status_code=204)
def delete_ativo(
    nome: str,
    db: Session = Depends(get_db),
    current_service: models.ServiceAccount = Depends(auth.get_current_actor)
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