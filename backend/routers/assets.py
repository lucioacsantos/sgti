from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, or_
from sqlalchemy.orm import selectinload
from typing import List, Optional

from database import get_db
from models import Ativo, TipoAtivo
from schemas import AssetCreate, AssetUpdate, AssetResponse
from security import get_current_user, require_groups

from audit import log_create, log_update, log_delete
import copy

from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from routers.auth import ServiceAccount

security = HTTPBearer()

router = APIRouter(prefix="/ativos", tags=["Ativos"])

async def verify_token(
    auth: HTTPAuthorizationCredentials = Depends(security),
    db: AsyncSession = Depends(get_db)
):
    result = await db.execute(
        select(ServiceAccount).where(ServiceAccount.token == auth.credentials)
    )
    account = result.scalar_one_or_none()
    
    if not account or not account.is_valid():
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token de automação inválido ou expirado"
        )
    return account


@router.post(
    "/",
    response_model=AssetResponse,
    status_code=201,
    dependencies=[Depends(require_groups("cmdb-admin"))]
)
async def create_asset(
    asset: AssetCreate,
    db: AsyncSession = Depends(get_db),
    user=Depends(get_current_user)
):
    db_asset = Ativo(**asset.model_dump())

    db_asset.created_by = user.subject

    db.add(db_asset)
    await db.flush()
    await log_create(db, "ativo", db_asset, user)
    await db.refresh(db_asset)

    return db_asset


@router.get(
    "/",
    response_model=List[AssetResponse],
    dependencies=[Depends(get_current_user)]
)
async def list_assets(
    search: Optional[str] = Query(None),
    db: AsyncSession = Depends(get_db)
):
    query = select(Ativo).options(selectinload(Ativo.tipo))

    if search:
        query = query.join(TipoAtivo).where(
            or_(
                Ativo.nome.ilike(f"%{search}%"),
                Ativo.responsavel.ilike(f"%{search}%"),
                TipoAtivo.nome.ilike(f"%{search}%")
            )
        )

    result = await db.execute(query.order_by(Ativo.nome))
    return result.scalars().all()


@router.get("/{asset_id}", response_model=AssetResponse)
async def get_asset(asset_id: int, db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(Ativo)
        .options(selectinload(Ativo.tipo))
        .where(Ativo.id == asset_id)
    )

    asset = result.scalar_one_or_none()

    if not asset:
        raise HTTPException(404, "Ativo não encontrado")

    return asset


@router.put(
    "/{asset_id}",
    response_model=AssetResponse,
    dependencies=[Depends(require_groups("cmdb-admin"))]
)
async def update_asset(
    asset_id: int,
    asset_update: AssetUpdate,
    db: AsyncSession = Depends(get_db),
    user=Depends(get_current_user)
):
    result = await db.execute(select(Ativo).where(Ativo.id == asset_id))
    db_asset = result.scalar_one_or_none()

    if not db_asset:
        raise HTTPException(404, "Ativo não encontrado")

    before = copy.deepcopy(db_asset)

    for key, value in asset_update.model_dump(exclude_unset=True).items():
        setattr(db_asset, key, value)

    db_asset.updated_by = user.subject

    await db.flush()
    await log_update(db, "ativo", before, db_asset, user)
    await db.refresh(db_asset)

    return db_asset


@router.delete(
    "/{asset_id}",
    dependencies=[Depends(require_groups("cmdb-admin"))],
    status_code=204
)
async def delete_asset(
    asset_id: int,
    db: AsyncSession = Depends(get_db),
    user=Depends(get_current_user)
):
    db_asset = await db.get(Ativo, asset_id)

    if not db_asset:
        raise HTTPException(404, "Ativo não encontrado")

    await log_delete(db, "ativo", db_asset, user)
    await db.delete(db_asset)