from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from typing import List

from database import get_db
from models import Ativo, Relacionamento
from schemas import RelationshipCreate
from security import get_current_user, require_groups

router = APIRouter(prefix="/relacionamentos", tags=["Relacionamentos"])


@router.post(
    "/",
    status_code=201,
    dependencies=[Depends(require_groups("cmdb-admin"))]
)
async def create_relationship(
    payload: RelationshipCreate,
    db: AsyncSession = Depends(get_db)
):
    if payload.origem_id == payload.destino_id:
        raise HTTPException(400, "Auto-relacionamento não permitido")

    # valida ativos
    result = await db.execute(
        select(Ativo).where(Ativo.id.in_([payload.origem_id, payload.destino_id]))
    )
    if len(result.scalars().all()) != 2:
        raise HTTPException(404, "Ativo não encontrado")

    rel = Relacionamento(**payload.model_dump())

    db.add(rel)
    await db.flush()

    return rel


@router.get(
    "/",
    dependencies=[Depends(get_current_user)]
)
async def list_relationships(db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(Relacionamento)
        .options(
            selectinload(Relacionamento.origem),
            selectinload(Relacionamento.destino),
            selectinload(Relacionamento.tipo)
        )
    )

    return result.scalars().all()


@router.delete(
    "/{rel_id}",
    dependencies=[Depends(require_groups("cmdb-admin"))],
    status_code=204
)
async def delete_relationship(rel_id: int, db: AsyncSession = Depends(get_db)):
    rel = await db.get(Relacionamento, rel_id)

    if not rel:
        raise HTTPException(404, "Relacionamento não encontrado")

    await db.delete(rel)