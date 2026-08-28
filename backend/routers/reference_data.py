from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from typing import Optional
import models, schemas, auth
from database import get_db
import logging

logger = logging.getLogger(__name__)

router = APIRouter(tags=["Dados Auxiliares"])


@router.get("/tipos-ativos/", response_model=list[schemas.TipoAtivoResponse])
def read_tipos_ativos(
    db: Session = Depends(get_db),
    current_service: models.ServiceAccount = Depends(auth.get_current_actor)
):
    logger.debug("Listing asset types", extra={"service_account": current_service.name})
    return db.query(models.TipoAtivo).all()


@router.get("/status-ativos/", response_model=list[schemas.StatusAtivoResponse])
def read_status_ativos(
    db: Session = Depends(get_db),
    current_service: models.ServiceAccount = Depends(auth.get_current_actor)
):
    logger.debug("Listing asset statuses", extra={"service_account": current_service.name})
    return db.query(models.StatusAtivo).all()


@router.get("/ambientes/", response_model=list[schemas.AmbienteResponse])
def read_ambientes(
    db: Session = Depends(get_db),
    current_service: models.ServiceAccount = Depends(auth.get_current_actor)
):
    logger.debug("Listing environments", extra={"service_account": current_service.name})
    return db.query(models.Ambiente).all()


@router.get("/criticidades/", response_model=list[schemas.CriticidadeResponse])
def read_criticidades(
    db: Session = Depends(get_db),
    current_service: models.ServiceAccount = Depends(auth.get_current_actor)
):
    logger.debug("Listing criticities", extra={"service_account": current_service.name})
    return db.query(models.Criticidade).all()


@router.post("/sistema-operacional/", response_model=schemas.SistemaOperacionalResponse, status_code=201)
def create_sistema_operacional(
    sistema_operacional: schemas.SistemaOperacionalCreate,
    db: Session = Depends(get_db),
    current_service: models.ServiceAccount = Depends(auth.get_current_actor)
):
    logger.info("Creating OS", extra={"service_account": current_service.name, "os_abbreviation": sistema_operacional.abreviacao})
    db_sistema_operacional = models.SistemaOperacional(**sistema_operacional.model_dump(exclude_unset=True))
    db.add(db_sistema_operacional)
    db.commit()
    db.refresh(db_sistema_operacional)
    return db_sistema_operacional


@router.get("/sistema-operacional/", response_model=list[schemas.SistemaOperacionalResponse])
def read_sistemas_operacionais(
    db: Session = Depends(get_db),
    current_service: models.ServiceAccount = Depends(auth.get_current_actor)
):
    logger.debug("Listing operating systems", extra={"service_account": current_service.name})
    return db.query(models.SistemaOperacional).all()


@router.get("/areas/", response_model=list[schemas.AreasResponse])
def read_areas(
    db: Session = Depends(get_db),
    current_service: models.ServiceAccount = Depends(auth.get_current_actor)
):
    logger.debug("Listing areas", extra={"service_account": current_service.name})
    return db.query(models.Areas).all()


# Admin CRUD endpoints for reference data
# Areas
@router.post("/admin/areas", response_model=schemas.AreasResponse, status_code=201)
def create_area(
    area: schemas.AreasResponse,
    db: Session = Depends(get_db),
    current_service: models.ServiceAccount = Depends(auth.get_current_actor)
):
    logger.info("Creating area", extra={"service_account": current_service.name, "area_nome": area.nome})
    db_area = models.Areas(nome=area.nome, sigla=area.sigla)
    db.add(db_area)
    db.commit()
    db.refresh(db_area)
    return db_area


@router.put("/admin/areas/{area_id}", response_model=schemas.AreasResponse)
def update_area(
    area_id: int,
    area: schemas.AreasResponse,
    db: Session = Depends(get_db),
    current_service: models.ServiceAccount = Depends(auth.get_current_actor)
):
    logger.info("Updating area", extra={"service_account": current_service.name, "area_id": area_id})
    db_area = db.query(models.Areas).filter(models.Areas.id == area_id).first()
    if not db_area:
        raise HTTPException(status_code=404, detail="Área não encontrada")
    db_area.nome = area.nome
    db_area.sigla = area.sigla
    db.commit()
    db.refresh(db_area)
    return db_area


@router.delete("/admin/areas/{area_id}", status_code=204)
def delete_area(
    area_id: int,
    db: Session = Depends(get_db),
    current_service: models.ServiceAccount = Depends(auth.get_current_actor)
):
    logger.info("Deleting area", extra={"service_account": current_service.name, "area_id": area_id})
    db_area = db.query(models.Areas).filter(models.Areas.id == area_id).first()
    if not db_area:
        raise HTTPException(status_code=404, detail="Área não encontrada")
    db.delete(db_area)
    db.commit()


# Asset Types
@router.post("/admin/asset-types", response_model=schemas.TipoAtivoResponse, status_code=201)
def create_asset_type(
    tipo: schemas.TipoAtivoResponse,
    db: Session = Depends(get_db),
    current_service: models.ServiceAccount = Depends(auth.get_current_actor)
):
    logger.info("Creating asset type", extra={"service_account": current_service.name, "tipo_nome": tipo.nome})
    db_tipo = models.TipoAtivo(nome=tipo.nome)
    db.add(db_tipo)
    db.commit()
    db.refresh(db_tipo)
    return db_tipo


@router.put("/admin/asset-types/{tipo_id}", response_model=schemas.TipoAtivoResponse)
def update_asset_type(
    tipo_id: int,
    tipo: schemas.TipoAtivoResponse,
    db: Session = Depends(get_db),
    current_service: models.ServiceAccount = Depends(auth.get_current_actor)
):
    logger.info("Updating asset type", extra={"service_account": current_service.name, "tipo_id": tipo_id})
    db_tipo = db.query(models.TipoAtivo).filter(models.TipoAtivo.id == tipo_id).first()
    if not db_tipo:
        raise HTTPException(status_code=404, detail="Tipo de ativo não encontrado")
    db_tipo.nome = tipo.nome
    db.commit()
    db.refresh(db_tipo)
    return db_tipo


@router.delete("/admin/asset-types/{tipo_id}", status_code=204)
def delete_asset_type(
    tipo_id: int,
    db: Session = Depends(get_db),
    current_service: models.ServiceAccount = Depends(auth.get_current_actor)
):
    logger.info("Deleting asset type", extra={"service_account": current_service.name, "tipo_id": tipo_id})
    db_tipo = db.query(models.TipoAtivo).filter(models.TipoAtivo.id == tipo_id).first()
    if not db_tipo:
        raise HTTPException(status_code=404, detail="Tipo de ativo não encontrado")
    db.delete(db_tipo)
    db.commit()


# Environments
@router.post("/admin/environments", response_model=schemas.AmbienteResponse, status_code=201)
def create_environment(
    ambiente: schemas.AmbienteResponse,
    db: Session = Depends(get_db),
    current_service: models.ServiceAccount = Depends(auth.get_current_actor)
):
    logger.info("Creating environment", extra={"service_account": current_service.name, "ambiente_nome": ambiente.nome})
    db_ambiente = models.Ambiente(nome=ambiente.nome)
    db.add(db_ambiente)
    db.commit()
    db.refresh(db_ambiente)
    return db_ambiente


@router.put("/admin/environments/{ambiente_id}", response_model=schemas.AmbienteResponse)
def update_environment(
    ambiente_id: int,
    ambiente: schemas.AmbienteResponse,
    db: Session = Depends(get_db),
    current_service: models.ServiceAccount = Depends(auth.get_current_actor)
):
    logger.info("Updating environment", extra={"service_account": current_service.name, "ambiente_id": ambiente_id})
    db_ambiente = db.query(models.Ambiente).filter(models.Ambiente.id == ambiente_id).first()
    if not db_ambiente:
        raise HTTPException(status_code=404, detail="Ambiente não encontrado")
    db_ambiente.nome = ambiente.nome
    db.commit()
    db.refresh(db_ambiente)
    return db_ambiente


@router.delete("/admin/environments/{ambiente_id}", status_code=204)
def delete_environment(
    ambiente_id: int,
    db: Session = Depends(get_db),
    current_service: models.ServiceAccount = Depends(auth.get_current_actor)
):
    logger.info("Deleting environment", extra={"service_account": current_service.name, "ambiente_id": ambiente_id})
    db_ambiente = db.query(models.Ambiente).filter(models.Ambiente.id == ambiente_id).first()
    if not db_ambiente:
        raise HTTPException(status_code=404, detail="Ambiente não encontrado")
    db.delete(db_ambiente)
    db.commit()


# Statuses
@router.post("/admin/statuses", response_model=schemas.StatusAtivoResponse, status_code=201)
def create_status(
    status: schemas.StatusAtivoResponse,
    db: Session = Depends(get_db),
    current_service: models.ServiceAccount = Depends(auth.get_current_actor)
):
    logger.info("Creating status", extra={"service_account": current_service.name, "status_nome": status.nome})
    db_status = models.StatusAtivo(nome=status.nome)
    db.add(db_status)
    db.commit()
    db.refresh(db_status)
    return db_status


@router.put("/admin/statuses/{status_id}", response_model=schemas.StatusAtivoResponse)
def update_status(
    status_id: int,
    status: schemas.StatusAtivoResponse,
    db: Session = Depends(get_db),
    current_service: models.ServiceAccount = Depends(auth.get_current_actor)
):
    logger.info("Updating status", extra={"service_account": current_service.name, "status_id": status_id})
    db_status = db.query(models.StatusAtivo).filter(models.StatusAtivo.id == status_id).first()
    if not db_status:
        raise HTTPException(status_code=404, detail="Status não encontrado")
    db_status.nome = status.nome
    db.commit()
    db.refresh(db_status)
    return db_status


@router.delete("/admin/statuses/{status_id}", status_code=204)
def delete_status(
    status_id: int,
    db: Session = Depends(get_db),
    current_service: models.ServiceAccount = Depends(auth.get_current_actor)
):
    logger.info("Deleting status", extra={"service_account": current_service.name, "status_id": status_id})
    db_status = db.query(models.StatusAtivo).filter(models.StatusAtivo.id == status_id).first()
    if not db_status:
        raise HTTPException(status_code=404, detail="Status não encontrado")
    db.delete(db_status)
    db.commit()


# Criticities
@router.post("/admin/criticities", response_model=schemas.CriticidadeResponse, status_code=201)
def create_criticidade(
    criticidade: schemas.CriticidadeResponse,
    db: Session = Depends(get_db),
    current_service: models.ServiceAccount = Depends(auth.get_current_actor)
):
    logger.info("Creating criticidade", extra={"service_account": current_service.name, "criticidade_nivel": criticidade.nivel})
    db_criticidade = models.Criticidade(nivel=criticidade.nivel)
    db.add(db_criticidade)
    db.commit()
    db.refresh(db_criticidade)
    return db_criticidade


@router.put("/admin/criticities/{criticidade_id}", response_model=schemas.CriticidadeResponse)
def update_criticidade(
    criticidade_id: int,
    criticidade: schemas.CriticidadeResponse,
    db: Session = Depends(get_db),
    current_service: models.ServiceAccount = Depends(auth.get_current_actor)
):
    logger.info("Updating criticidade", extra={"service_account": current_service.name, "criticidade_id": criticidade_id})
    db_criticidade = db.query(models.Criticidade).filter(models.Criticidade.id == criticidade_id).first()
    if not db_criticidade:
        raise HTTPException(status_code=404, detail="Criticidade não encontrada")
    db_criticidade.nivel = criticidade.nivel
    db.commit()
    db.refresh(db_criticidade)
    return db_criticidade


@router.delete("/admin/criticities/{criticidade_id}", status_code=204)
def delete_criticidade(
    criticidade_id: int,
    db: Session = Depends(get_db),
    current_service: models.ServiceAccount = Depends(auth.get_current_actor)
):
    logger.info("Deleting criticidade", extra={"service_account": current_service.name, "criticidade_id": criticidade_id})
    db_criticidade = db.query(models.Criticidade).filter(models.Criticidade.id == criticidade_id).first()
    if not db_criticidade:
        raise HTTPException(status_code=404, detail="Criticidade não encontrada")
    db.delete(db_criticidade)
    db.commit()


# Operating Systems
@router.post("/admin/operating-systems", response_model=schemas.SistemaOperacionalResponse, status_code=201)
def create_operating_system_admin(
    so: schemas.SistemaOperacionalCreate,
    db: Session = Depends(get_db),
    current_service: models.ServiceAccount = Depends(auth.get_current_actor)
):
    logger.info("Creating OS (admin)", extra={"service_account": current_service.name, "so_abbreviation": so.abreviacao})
    db_so = models.SistemaOperacional(**so.model_dump(exclude_unset=True))
    db.add(db_so)
    db.commit()
    db.refresh(db_so)
    return db_so


@router.put("/admin/operating-systems/{so_id}", response_model=schemas.SistemaOperacionalResponse)
def update_operating_system_admin(
    so_id: int,
    so: schemas.SistemaOperacionalCreate,
    db: Session = Depends(get_db),
    current_service: models.ServiceAccount = Depends(auth.get_current_actor)
):
    logger.info("Updating OS (admin)", extra={"service_account": current_service.name, "so_id": so_id})
    db_so = db.query(models.SistemaOperacional).filter(models.SistemaOperacional.id == so_id).first()
    if not db_so:
        raise HTTPException(status_code=404, detail="Sistema operacional não encontrado")
    for campo, valor in so.model_dump(exclude_unset=True).items():
        setattr(db_so, campo, valor)
    db.commit()
    db.refresh(db_so)
    return db_so


@router.delete("/admin/operating-systems/{so_id}", status_code=204)
def delete_operating_system_admin(
    so_id: int,
    db: Session = Depends(get_db),
    current_service: models.ServiceAccount = Depends(auth.get_current_actor)
):
    logger.info("Deleting OS (admin)", extra={"service_account": current_service.name, "so_id": so_id})
    db_so = db.query(models.SistemaOperacional).filter(models.SistemaOperacional.id == so_id).first()
    if not db_so:
        raise HTTPException(status_code=404, detail="Sistema operacional não encontrado")
    db.delete(db_so)
    db.commit()


# Relationship Types
@router.get("/admin/relationship-types", response_model=list[schemas.TipoRelacionamentoResponse])
def read_tipos_relacionamento_admin(
    db: Session = Depends(get_db),
    current_service: models.ServiceAccount = Depends(auth.get_current_actor)
):
    logger.debug("Listing relationship types (admin)", extra={"service_account": current_service.name})
    return db.query(models.TipoRelacionamento).all()


@router.post("/admin/relationship-types", response_model=schemas.TipoRelacionamentoResponse, status_code=201)
def create_tipo_relacionamento_admin(
    tipo: schemas.TipoRelacionamentoCreate,
    db: Session = Depends(get_db),
    current_service: models.ServiceAccount = Depends(auth.get_current_actor)
):
    logger.info("Creating relationship type (admin)", extra={"service_account": current_service.name, "tipo_nome": tipo.nome})
    db_tipo = models.TipoRelacionamento(**tipo.model_dump(exclude_unset=True))
    db.add(db_tipo)
    db.commit()
    db.refresh(db_tipo)
    return db_tipo


@router.put("/admin/relationship-types/{tipo_id}", response_model=schemas.TipoRelacionamentoResponse)
def update_tipo_relacionamento_admin(
    tipo_id: int,
    tipo: schemas.TipoRelacionamentoCreate,
    db: Session = Depends(get_db),
    current_service: models.ServiceAccount = Depends(auth.get_current_actor)
):
    logger.info("Updating relationship type (admin)", extra={"service_account": current_service.name, "tipo_id": tipo_id})
    db_tipo = db.query(models.TipoRelacionamento).filter(models.TipoRelacionamento.id == tipo_id).first()
    if not db_tipo:
        raise HTTPException(status_code=404, detail="Tipo de relacionamento não encontrado")
    for campo, valor in tipo.model_dump(exclude_unset=True).items():
        setattr(db_tipo, campo, valor)
    db.commit()
    db.refresh(db_tipo)
    return db_tipo


@router.delete("/admin/relationship-types/{tipo_id}", status_code=204)
def delete_tipo_relacionamento_admin(
    tipo_id: int,
    db: Session = Depends(get_db),
    current_service: models.ServiceAccount = Depends(auth.get_current_actor)
):
    logger.info("Deleting relationship type (admin)", extra={"service_account": current_service.name, "tipo_id": tipo_id})
    db_tipo = db.query(models.TipoRelacionamento).filter(models.TipoRelacionamento.id == tipo_id).first()
    if not db_tipo:
        raise HTTPException(status_code=404, detail="Tipo de relacionamento não encontrado")
    db.delete(db_tipo)
    db.commit()