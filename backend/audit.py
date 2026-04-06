from models import AuditLog
from sqlalchemy.ext.asyncio import AsyncSession


EXCLUDE_FIELDS = {"token_hash"}

def to_dict(obj):
    return {
        c.name: getattr(obj, c.name)
        for c in obj.__table__.columns
        if c.name not in EXCLUDE_FIELDS
    }


async def log_create(db: AsyncSession, entidade, obj, user):
    db.add(AuditLog(
        entidade=entidade,
        entidade_id=obj.id,
        acao="CREATE",
        antes=None,
        depois=to_dict(obj),
        usuario=user.subject
    ))


async def log_update(db: AsyncSession, entidade, before, after, user):
    db.add(AuditLog(
        entidade=entidade,
        entidade_id=after.id,
        acao="UPDATE",
        antes=to_dict(before),
        depois=to_dict(after),
        usuario=user.subject
    ))


async def log_delete(db: AsyncSession, entidade, obj, user):
    db.add(AuditLog(
        entidade=entidade,
        entidade_id=obj.id,
        acao="DELETE",
        antes=to_dict(obj),
        depois=None,
        usuario=user.subject
    ))