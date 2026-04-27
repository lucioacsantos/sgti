from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from datetime import datetime, timedelta

from database import get_db
from models import ApiToken
from token_utils import generate_token, hash_token
from security import require_groups

router = APIRouter(prefix="/tokens", tags=["Tokens"])


@router.post("/", dependencies=[Depends(require_groups("cmdb-admin"))])
async def create_token(nome: str, db: AsyncSession = Depends(get_db)):

    raw_token = generate_token()

    db_token = ApiToken(
        nome=nome,
        token_hash=hash_token(raw_token),
        expira_em=datetime.utcnow() + timedelta(days=90)
    )

    db.add(db_token)
    await db.flush()

    return {
        "token": raw_token,
        "expira_em": db_token.expira_em
    }


@router.post("/{token_id}/rotate", dependencies=[Depends(require_groups("cmdb-admin"))])
async def rotate_token(token_id: int, db: AsyncSession = Depends(get_db)):

    result = await db.execute(select(ApiToken).where(ApiToken.id == token_id))
    db_token = result.scalar_one_or_none()

    if not db_token:
        raise HTTPException(404, "Token não encontrado")

    new_token = generate_token()
    db_token.token_hash = hash_token(new_token)
    db_token.expira_em = datetime.utcnow() + timedelta(days=90)

    await db.flush()

    return {"token": new_token}


@router.delete("/{token_id}", dependencies=[Depends(require_groups("cmdb-admin"))])
async def revoke_token(token_id: int, db: AsyncSession = Depends(get_db)):

    result = await db.execute(select(ApiToken).where(ApiToken.id == token_id))
    db_token = result.scalar_one_or_none()

    if not db_token:
        raise HTTPException(404, "Token não encontrado")

    db_token.ativo = False
    await db.flush()

    return {"message": "Token revogado"}