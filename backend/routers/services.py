from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import selectinload
from sqlalchemy.ext.asyncio import AsyncSession

from database import get_db
from models import DadosServico, Asset
from schemas import ServiceCreate, ServiceResponse

router = APIRouter(prefix="/services", tags=["Serviços"])

# ============================================
# LISTAR SERVIÇOS
# ============================================
@router.get("/", response_model=list[ServiceResponse])
async def list_services(db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(DadosServico)
        .options(selectinload(DadosServico.hosts))
    )
    return result.scalars().all()

# ============================================
# BUSCAR SERVIÇO ESPECÍFICO
# ============================================
@router.get("/{service_id}", response_model=ServiceResponse)
async def get_service(service_id: int, db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(DadosServico)
        .where(DadosServico.id == service_id)
        .options(selectinload(DadosServico.hosts))
    )
    service = result.scalars().first()

    if not service:
        raise HTTPException(404, "Serviço não encontrado")

    return service

# ============================================
# CRIAR SERVIÇO
# ============================================
@router.post("/", response_model=ServiceResponse)
async def create_service(payload: ServiceCreate, db: AsyncSession = Depends(get_db)):

    service = DadosServico(
        tipo_servico=payload.tipo_servico,
        nome_servico=payload.nome_servico,
        servico_stop=payload.servico_stop,
        servico_start=payload.servico_start,
        servico_validacao=payload.servico_validacao,
        servico_usuario=payload.servico_usuario,
    )
    db.add(service)
    await db.commit()
    await db.refresh(service)

    # Relacionar hosts
    if payload.host_ids:
        result = await db.execute(
            select(Asset).where(Asset.id.in_(payload.host_ids))
        )
        assets = result.scalars().all()
        service.hosts = assets

        await db.commit()
        await db.refresh(service)

    return service

# ============================================
# ATUALIZAR SERVIÇO
# ============================================
@router.put("/{service_id}", response_model=ServiceResponse)
async def update_service(service_id: int, payload: ServiceCreate, db: AsyncSession = Depends(get_db)):

    result = await db.execute(
        select(DadosServico).where(DadosServico.id == service_id)
    )
    service = result.scalars().first()

    if not service:
        raise HTTPException(404, "Serviço não encontrado")

    # Atualizar campos
    for k, v in payload.dict(exclude={"host_ids"}).items():
        setattr(service, k, v)

    # Atualizar hosts
    result = await db.execute(
        select(Asset).where(Asset.id.in_(payload.host_ids))
    )
    service.hosts = result.scalars().all()

    await db.commit()
    await db.refresh(service)

    return service

# ============================================
# DELETAR SERVIÇO
# ============================================
@router.delete("/{service_id}")
async def delete_service(service_id: int, db: AsyncSession = Depends(get_db)):
    service = await db.get(DadosServico, service_id)

    if not service:
        raise HTTPException(404, "Serviço não encontrado")

    await db.delete(service)
    await db.commit()

    return {"message": "Serviço deletado com sucesso"}
