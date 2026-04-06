from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from database import get_db
from models import Ativo
from security import get_current_user

router = APIRouter(prefix="/servicos", tags=["Serviços"])


@router.get("/", dependencies=[Depends(get_current_user)])
async def list_services(db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(Ativo).where(Ativo.tipo_id == 3)  # exemplo: tipo "servico"
    )
    return result.scalars().all()