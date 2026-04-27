from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from datetime import datetime
import os
import jwt

from database import get_db
from models import ApiToken

security = HTTPBearer()

DEV_MODE = os.getenv("DEV_MODE", "false").lower() == "true"


class AuthContext:
    def __init__(self, type, subject, groups=None):
        self.type = type
        self.subject = subject
        self.groups = groups or []


# =========================
# TOKEN DB VALIDATION
# =========================

from token_utils import hash_token

async def validate_api_token(token: str, db: AsyncSession):
    token_h = hash_token(token)

    result = await db.execute(
        select(ApiToken).where(
            ApiToken.token_hash == token_h,
            ApiToken.ativo == True
        )
    )
    db_token = result.scalar_one_or_none()

    if not db_token:
        return None

    if db_token.expira_em and db_token.expira_em < datetime.utcnow():
        return None

    return AuthContext(type="token", subject=db_token.nome)


# =========================
# OAUTH
# =========================

OAUTH_PUBLIC_KEY = os.getenv("OAUTH_PUBLIC_KEY")
OAUTH_ISSUER = os.getenv("OAUTH_ISSUER")
OAUTH_AUDIENCE = os.getenv("OAUTH_AUDIENCE")


def validate_oauth_token(token: str):
    if not OAUTH_PUBLIC_KEY:
        return None

    try:
        payload = jwt.decode(
            token,
            OAUTH_PUBLIC_KEY,
            algorithms=["RS256"],
            audience=OAUTH_AUDIENCE,
            issuer=OAUTH_ISSUER,
        )

        return AuthContext(
            type="oauth",
            subject=payload.get("preferred_username"),
            groups=payload.get("groups", [])
        )

    except Exception:
        return None


# =========================
# MAIN AUTH
# =========================

async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security),
    db: AsyncSession = Depends(get_db)
):
    token = credentials.credentials

    # DEV BYPASS
    if DEV_MODE and token == "dev-token":
        return AuthContext(type="dev", subject="dev-user", groups=["cmdb-admin"])

    # API TOKEN
    ctx = await validate_api_token(token, db)
    if ctx:
        return ctx

    # OAUTH
    ctx = validate_oauth_token(token)
    if ctx:
        return ctx

    raise HTTPException(401, "Invalid authentication")


# =========================
# AUTHORIZATION
# =========================

def require_groups(*groups_required):
    async def checker(user: AuthContext = Depends(get_current_user)):
        if user.type in ["token", "dev"]:
            return user

        if not set(user.groups).intersection(groups_required):
            raise HTTPException(403, "Access denied")

        return user

    return checker