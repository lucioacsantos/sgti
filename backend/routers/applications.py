from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
import models, schemas, auth
from database import get_db
import logging

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/aplicacoes", tags=["Aplicações"])


@router.post("/", response_model=schemas.AplicacaoResponse, status_code=201)
def create_aplicacao(
    aplicacao: schemas.AplicacaoCreate,
    db: Session = Depends(get_db),
    current_service: models.ServiceAccount = Depends(auth.get_service_account)
):
    logger.info("Creating application", extra={"service_account": current_service.name, "system": aplicacao.sistema})
    db_aplicacao = models.Aplicacao(**aplicacao.model_dump(exclude_unset=True))
    db.add(db_aplicacao)
    db.commit()
    db.refresh(db_aplicacao)
    return db_aplicacao


@router.get("/", response_model=list[schemas.AplicacaoResponse])
def read_aplicacoes(
    db: Session = Depends(get_db),
    current_service: models.ServiceAccount = Depends(auth.get_service_account)
):
    logger.debug("Listing applications", extra={"service_account": current_service.name})
    return db.query(models.Aplicacao).all()


@router.get("/{aplicacao_id}", response_model=schemas.AplicacaoResponse)
def read_aplicacao(
    aplicacao_id: int,
    db: Session = Depends(get_db),
    current_service: models.ServiceAccount = Depends(auth.get_service_account)
):
    logger.debug("Reading application", extra={"service_account": current_service.name, "aplicacao_id": aplicacao_id})
    aplicacao = db.query(models.Aplicacao).filter(models.Aplicacao.id == aplicacao_id).first()
    if not aplicacao:
        raise HTTPException(status_code=404, detail="Aplicação não encontrada")
    return aplicacao