from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from typing import List, Optional
from database import get_db
from models import Asset
from schemas import AssetCreate, AssetUpdate, AssetResponse, AssetWithRelationships

router = APIRouter(prefix="/assets", tags=["Assets"])

@router.post("/", response_model=AssetResponse, status_code=201, summary="Criar novo ativo")
async def create_asset(asset: AssetCreate, db: AsyncSession = Depends(get_db)):
    db_asset = Asset(**asset.model_dump())
    db.add(db_asset)
    await db.flush()
    await db.refresh(db_asset)
    return db_asset

@router.get("/", response_model=List[AssetResponse], summary="Listar todos os ativos")
async def list_assets(
    type: Optional[str] = Query(None, description="Filtrar por tipo de ativo"),
    owner: Optional[str] = Query(None, description="Filtrar por proprietário"),
    db: AsyncSession = Depends(get_db)
):
    query = select(Asset)
    if type:
        query = query.where(Asset.type == type)
    if owner:
        query = query.where(Asset.owner == owner)
    
    result = await db.execute(query)
    assets = result.scalars().all()
    return assets

@router.get("/{asset_id}", response_model=AssetWithRelationships, summary="Obter ativo por ID")
async def get_asset(asset_id: int, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Asset).where(Asset.id == asset_id))
    asset = result.scalar_one_or_none()
    if not asset:
        raise HTTPException(status_code=404, detail=f"Ativo com ID {asset_id} não encontrado")
    return asset

@router.put("/{asset_id}", response_model=AssetResponse, summary="Atualizar ativo")
async def update_asset(asset_id: int, asset_update: AssetUpdate, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Asset).where(Asset.id == asset_id))
    db_asset = result.scalar_one_or_none()
    if not db_asset:
        raise HTTPException(status_code=404, detail=f"Ativo com ID {asset_id} não encontrado")
    
    update_data = asset_update.model_dump(exclude_unset=True)
    for key, value in update_data.items():
        setattr(db_asset, key, value)
    
    await db.flush()
    await db.refresh(db_asset)
    return db_asset

@router.delete("/{asset_id}", status_code=204, summary="Deletar ativo")
async def delete_asset(asset_id: int, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Asset).where(Asset.id == asset_id))
    db_asset = result.scalar_one_or_none()
    if not db_asset:
        raise HTTPException(status_code=404, detail=f"Ativo com ID {asset_id} não encontrado")
    
    await db.delete(db_asset)
    return None
