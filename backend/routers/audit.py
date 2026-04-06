from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from typing import List

from database import get_db
from models import AuditLog
from security import require_groups

router = APIRouter(prefix="/audit", tags=["Audit"])


@router.get("/", dependencies=[Depends(require_groups("cmdb-admin"))])
async def list_audit(
    entidade: str = None,
    entidade_id: int = None,
    limit: int = 100,
    db: AsyncSession = Depends(get_db)
):

    query = select(AuditLog)

    if entidade:
        query = query.where(AuditLog.entidade == entidade)

    if entidade_id:
        query = query.where(AuditLog.entidade_id == entidade_id)

    query = query.order_by(AuditLog.id.desc()).limit(limit)

    result = await db.execute(query)

    return result.scalars().all()