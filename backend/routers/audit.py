from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from typing import Optional
import models, schemas, auth
from database import get_db
import logging

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/audit-logs", tags=["Audit Logs"])


@router.get("/", response_model=list[schemas.AuditLogResponse])
def read_audit_logs(
    entidade: Optional[str] = None,
    entidade_id: Optional[int] = None,
    skip: int = 0,
    limit: int = 50,
    db: Session = Depends(get_db),
    current_service: models.ServiceAccount = Depends(auth.get_service_account)
):
    query = db.query(models.AuditLog)
    if entidade:
        query = query.filter(models.AuditLog.entidade == entidade)
    if entidade_id:
        query = query.filter(models.AuditLog.entidade_id == entidade_id)
    return query.order_by(models.AuditLog.created_at.desc()).offset(skip).limit(min(limit, 100)).all()