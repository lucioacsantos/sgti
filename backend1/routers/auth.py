from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from datetime import datetime, timedelta
import secrets

from database import get_db
from models import ServiceAccount
from schemas import ServiceAccountCreate, ServiceAccountResponse


from pydantic import BaseModel
from jose import jwt
from ldap3 import Server, Connection, ALL, SUBTREE
import os

router = APIRouter(prefix="/auth", tags=["Autenticação"])


# Configurações (Idealmente no .env)
SECRET_KEY = os.getenv("JWT_SECRET_KEY", "uma-chave-muito-secreta-aqui")
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 480 # 8 horas de expediente


# GERAR TOKEN PARA ANSIBLE (Service Account)
@router.post("/tokens", response_model=ServiceAccountResponse)
async def generate_automation_token(
    payload: ServiceAccountCreate, 
    db: AsyncSession = Depends(get_db)
):
    # Gera um token seguro de 64 caracteres
    random_token = secrets.token_urlsafe(48)
    expiration = datetime.utcnow() + timedelta(days=payload.days_valid)
    
    new_account = ServiceAccount(
        name=payload.name,
        token=random_token,
        expires_at=expiration
    )
    
    db.add(new_account)
    await db.flush() # Salva mas aguarda o commit automático do get_db
    
    return new_account


# LOGIN LDAP (Placeholder para o próximo passo)
@router.post("/login-ldap")
async def login_ldap(username: str, password: str):
    # Aqui entrará a lógica da biblioteca ldap3 que discutimos
    return {"message": "Lógica LDAP em implementação"}


# --- SCHEMAS ---
class LoginRequest(BaseModel):
    username: str
    password: str


# --- LÓGICA LDAP ---
def verify_ldap_credentials(username, password):
    ldap_server = "ldaps://seu-ad.energia.org.br:636" # Use LDAPS para segurança
    base_dn = "DC=energia,DC=org,DC=br"
    user_dn = f"{username}@energia.org.br"
    # Grupo que tem permissão de acesso
    group_dn = "CN=SGTI_USUARIOS,OU=Groups,DC=energia,DC=org,DC=br"

    server = Server(ldap_server, get_info=ALL)
    try:
        # Tenta o BIND (Login)
        with Connection(server, user=user_dn, password=password, auto_bind=True) as conn:
            # Verifica se é membro do grupo
            search_filter = f"(&(sAMAccountName={username})(memberOf={group_dn}))"
            conn.search(base_dn, search_filter, search_scope=SUBTREE)
            return len(conn.entries) > 0
    except Exception:
        return False


# --- ROTA DE LOGIN ---
@router.post("/login")
async def login_via_ad(payload: LoginRequest):
    if not verify_ldap_credentials(payload.username, payload.password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Usuário/Senha inválidos ou sem permissão de grupo"
        )
    
    # Gera o JWT
    expire = datetime.utcnow() + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    to_encode = {"sub": payload.username, "exp": expire, "role": "admin"}
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    
    return {"access_token": encoded_jwt, "token_type": "bearer"}