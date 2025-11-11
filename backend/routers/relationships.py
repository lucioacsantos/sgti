from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, insert, delete
from typing import List
from backend.database import get_db
from backend.models import Asset, asset_relationships
from backend.schemas import RelationshipCreate, RelationshipResponse

router = APIRouter(prefix="/relationships", tags=["Relationships"])

@router.post("/", response_model=RelationshipResponse, status_code=201, summary="Criar relacionamento entre ativos")
async def create_relationship(relationship: RelationshipCreate, db: AsyncSession = Depends(get_db)):
    result_source = await db.execute(select(Asset).where(Asset.id == relationship.source_asset_id))
    source_asset = result_source.scalar_one_or_none()
    if not source_asset:
        raise HTTPException(status_code=404, detail=f"Ativo de origem com ID {relationship.source_asset_id} não encontrado")
    
    result_target = await db.execute(select(Asset).where(Asset.id == relationship.target_asset_id))
    target_asset = result_target.scalar_one_or_none()
    if not target_asset:
        raise HTTPException(status_code=404, detail=f"Ativo de destino com ID {relationship.target_asset_id} não encontrado")
    
    if relationship.source_asset_id == relationship.target_asset_id:
        raise HTTPException(status_code=400, detail="Um ativo não pode se relacionar consigo mesmo")
    
    stmt = insert(asset_relationships).values(
        source_asset_id=relationship.source_asset_id,
        target_asset_id=relationship.target_asset_id,
        relationship_type=relationship.relationship_type
    )
    
    try:
        await db.execute(stmt)
        await db.flush()
    except Exception:
        raise HTTPException(status_code=400, detail="Relacionamento já existe ou erro ao criar")
    
    return RelationshipResponse(
        source_asset_id=relationship.source_asset_id,
        target_asset_id=relationship.target_asset_id,
        relationship_type=relationship.relationship_type,
        source_asset=source_asset,
        target_asset=target_asset
    )

@router.get("/", response_model=List[RelationshipResponse], summary="Listar todos os relacionamentos")
async def list_relationships(db: AsyncSession = Depends(get_db)):
    query = select(asset_relationships)
    result = await db.execute(query)
    relationships = result.all()
    
    response_list = []
    for rel in relationships:
        source_result = await db.execute(select(Asset).where(Asset.id == rel.source_asset_id))
        source_asset = source_result.scalar_one()
        
        target_result = await db.execute(select(Asset).where(Asset.id == rel.target_asset_id))
        target_asset = target_result.scalar_one()
        
        response_list.append(RelationshipResponse(
            source_asset_id=rel.source_asset_id,
            target_asset_id=rel.target_asset_id,
            relationship_type=rel.relationship_type,
            source_asset=source_asset,
            target_asset=target_asset
        ))
    
    return response_list

@router.delete("/{source_id}/{target_id}", status_code=204, summary="Deletar relacionamento")
async def delete_relationship(source_id: int, target_id: int, db: AsyncSession = Depends(get_db)):
    query = select(asset_relationships).where(
        asset_relationships.c.source_asset_id == source_id,
        asset_relationships.c.target_asset_id == target_id
    )
    result = await db.execute(query)
    existing = result.first()
    
    if not existing:
        raise HTTPException(status_code=404, detail="Relacionamento não encontrado")
    
    stmt = delete(asset_relationships).where(
        asset_relationships.c.source_asset_id == source_id,
        asset_relationships.c.target_asset_id == target_id
    )
    await db.execute(stmt)
    
    return None
