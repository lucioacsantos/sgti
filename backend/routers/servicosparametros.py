from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from typing import List, Optional
from database import get_db
from models import Asset
from schemas import AssetCreate, AssetUpdate, AssetResponse, AssetWithRelationships

router = APIRouter(prefix="/servicosparametros", tags=["ServicosParametros"])

@router.post("/", response_model=AssetResponse, status_code=201, summary="Criar novo serviço/parametro")
async def create_servico_parametro(servico_parametro: AssetCreate, db: AsyncSession = Depends(get_db)):
    db_servico_parametro = Asset(**servico_parametro.model_dump())
    db.add(db_servico_parametro)
    await db.flush()
    await db.refresh(db_servico_parametro)
    return db_servico_parametro