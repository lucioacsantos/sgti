from sqlalchemy.orm import Session
import models
from datetime import datetime, timezone
import json


def create_audit_log(
    db: Session,
    entidade: str,
    entidade_id: int | None,
    acao: str,
    antes: dict | None = None,
    depois: dict | None = None,
    usuario: str | None = None,
) -> None:
    """Create an audit log entry."""
    audit = models.AuditLog(
        entidade=entidade,
        entidade_id=entidade_id,
        acao=acao,
        antes=antes,
        depois=depois,
        usuario=usuario,
        created_at=datetime.now(timezone.utc),
    )
    db.add(audit)
    db.flush()


def model_to_dict(obj, exclude: set[str] | None = None) -> dict:
    """Convert SQLAlchemy model to dictionary for audit logging."""
    if obj is None:
        return {}
    exclude = exclude or {"created_at", "updated_at"}
    return {
        c.key: getattr(obj, c.key)
        for c in obj.__table__.columns
        if c.key not in exclude
    }