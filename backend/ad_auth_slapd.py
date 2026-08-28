"""
Active Directory / LDAP Authentication Module
"""
import ldap3
from ldap3 import Server, Connection, ALL, SUBTREE, SIMPLE, Tls, ALL_ATTRIBUTES
from ldap3.core.exceptions import LDAPException
from typing import Optional, List, Dict, Any
from datetime import datetime, timedelta
from sqlalchemy.orm import Session
import models
import schemas
from database import get_db
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
import jwt
import os
import ssl
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

# JWT Settings
SECRET_KEY = os.getenv("JWT_SECRET_KEY", "your-secret-key-change-in-production")
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = int(os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES", "30"))
REFRESH_TOKEN_EXPIRE_DAYS = int(os.getenv("REFRESH_TOKEN_EXPIRE_DAYS", "7"))

# AD/LDAP Settings
AD_SERVER = os.getenv("AD_SERVER", "ldap://pwdc01.energia.org.br")
AD_PORT = int(os.getenv("AD_PORT", "389"))
AD_DOMAIN = os.getenv("AD_DOMAIN", "energia.org.br")
AD_BASE_DN = os.getenv("AD_BASE_DN", "DC=energia,DC=org,DC=br")
AD_BIND_DN = os.getenv("AD_BIND_DN", "")
AD_BIND_PASSWORD = os.getenv("AD_BIND_PASSWORD", "")
AD_USE_SSL = os.getenv("AD_USE_SSL", "false").lower() == "true"
AD_SEARCH_FILTER = os.getenv("AD_SEARCH_FILTER", "(sAMAccountName={username})")
AD_GROUP_SEARCH_FILTER = os.getenv("AD_GROUP_SEARCH_FILTER", "(member={user_dn})")


def get_role_mapping() -> Dict[str, List[str]]:
    """Carrega mapeamento de roles do .env (ex: ROLE_ADMIN=G_GESIN_GOSD_OMIS)"""
    mapping = {}
    for key, value in os.environ.items():
        if key.startswith("ROLE_"):
            role_name = key.replace("ROLE_", "").lower()
            groups = [g.strip() for g in value.split(",")]
            mapping[role_name] = groups
    return mapping


class ADAuthError(Exception):
    """Custom exception for AD authentication errors"""
    pass


def _create_server() -> Server:
    """Instancia o servidor LDAP com suporte a SSL/TLS se configurado"""
    tls_config = Tls(validate=ssl.CERT_NONE) if AD_USE_SSL else None
    return Server(AD_SERVER, port=AD_PORT, get_info=ALL, use_ssl=AD_USE_SSL, tls=tls_config)


def get_ad_connection() -> Connection:
    """Cria conexão usando a conta de serviço com autenticação SIMPLE"""
    try:
        server = _create_server()
        if AD_BIND_DN and AD_BIND_PASSWORD:
            user = AD_BIND_DN if "@" in AD_BIND_DN or "=" in AD_BIND_DN else f"{AD_BIND_DN}@{AD_DOMAIN}"
            conn = Connection(
                server,
                user=user,
                password=AD_BIND_PASSWORD,
                authentication=SIMPLE,
                auto_bind=True
            )
        else:
            conn = Connection(server, auto_bind=True)
        return conn
    except LDAPException as e:
        raise ADAuthError(f"Failed to connect to AD: {str(e)}")


def authenticate_user(username: str, password: str) -> Optional[Dict[str, Any]]:
    try:
        server = _create_server()
        
        # 1. Conecta via conta de serviço para localizar o DN do usuário
        service_conn = get_ad_connection()
        clean_username = username.split("@")[0]
        search_filter = AD_SEARCH_FILTER.format(username=clean_username)
        
        # Solicita ALL_ATTRIBUTES ('*') para evitar erro de schema inexistente
        service_conn.search(
            search_base=AD_BASE_DN,
            search_filter=search_filter,
            search_scope=SUBTREE,
            attributes=ALL_ATTRIBUTES
        )
        
        if not service_conn.entries:
            service_conn.unbind()
            return None
        
        entry = service_conn.entries[0]
        user_dn = entry.entry_dn
        service_conn.unbind()
        
        # 2. Realiza o Bind com o DN localizado e a senha do usuário
        user_conn = Connection(
            server,
            user=user_dn,
            password=password,
            authentication=SIMPLE,
            auto_bind=True
        )
        
        if not user_conn.bound:
            return None
        
        user_conn.unbind()
        
        # 3. Extrai grupos
        groups = []
        if hasattr(entry, 'memberOf') and entry.memberOf:
            for group_dn in entry.memberOf.values:
                groups.append(str(group_dn))
        
        # Resolve username para OpenLDAP (uid) ou Active Directory (sAMAccountName)
        account_name = str(entry.uid) if hasattr(entry, 'uid') and entry.uid else (
            str(entry.sAMAccountName) if hasattr(entry, 'sAMAccountName') and entry.sAMAccountName else clean_username
        )
        
        # Resolve displayName
        display_name = str(entry.displayName) if hasattr(entry, 'displayName') and entry.displayName else (
            str(entry.cn) if hasattr(entry, 'cn') and entry.cn else account_name
        )
        
        user_info = {
            "username": account_name,
            "display_name": display_name,
            "email": str(entry.mail) if hasattr(entry, 'mail') and entry.mail else f"{clean_username}@{AD_DOMAIN.lower()}",
            "user_principal_name": str(entry.userPrincipalName) if hasattr(entry, 'userPrincipalName') and entry.userPrincipalName else None,
            "distinguished_name": user_dn,
            "groups": groups,
            "given_name": str(entry.givenName) if hasattr(entry, 'givenName') and entry.givenName else None,
            "surname": str(entry.sn) if hasattr(entry, 'sn') and entry.sn else None,
        }
        
        return user_info
        
    except LDAPException as e:
        raise ADAuthError(f"AD/LDAP authentication failed: {str(e)}")


def map_ad_groups_to_roles(ad_groups: List[str]) -> List[str]:
    """Mapeia grupos do AD para roles da aplicação com base no .env"""
    roles = []
    role_map = get_role_mapping()
    
    for group in ad_groups:
        group_cn = group.split(',')[0].replace('CN=', '') if 'CN=' in group else group
        
        for role, groups in role_map.items():
            if any(g.lower() in group.lower() or g.lower() == group_cn.lower() for g in groups):
                roles.append(role)
    
    if not roles:
        roles = ["viewer"]
    
    return list(set(roles))


def create_or_update_local_user(db: Session, ad_user: Dict[str, Any]) -> models.ServiceAccount:
    """Cria ou atualiza usuário no banco local"""
    import json
    username = ad_user["username"]
    local_user = db.query(models.ServiceAccount).filter(
        models.ServiceAccount.name == username
    ).first()
    
    roles = map_ad_groups_to_roles(ad_user.get("groups", []))
    payload_data = json.dumps({"roles": roles, "ad_user": True, "email": ad_user.get("email")})
    
    if local_user:
        local_user.is_active = True
        local_user.expires_at = datetime.utcnow() + timedelta(days=365)
        local_user.token_hash = payload_data
    else:
        local_user = models.ServiceAccount(
            name=username,
            token_hash=payload_data,
            expires_at=datetime.utcnow() + timedelta(days=365),
            is_active=True,
        )
        db.add(local_user)
    
    db.commit()
    db.refresh(local_user)
    return local_user


def create_access_token(data: dict, expires_delta: Optional[timedelta] = None) -> str:
    to_encode = data.copy()
    expire = datetime.utcnow() + (expires_delta if expires_delta else timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES))
    to_encode.update({"exp": expire, "type": "access"})
    return jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)


def create_refresh_token(data: dict) -> str:
    to_encode = data.copy()
    expire = datetime.utcnow() + timedelta(days=REFRESH_TOKEN_EXPIRE_DAYS)
    to_encode.update({"exp": expire, "type": "refresh"})
    return jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)


def decode_token(token: str) -> Optional[dict]:
    try:
        return jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
    except (jwt.ExpiredSignatureError, jwt.JWTError):
        return None


oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/auth/ad/login")


def get_current_user(
    token: str = Depends(oauth2_scheme),
    db: Session = Depends(get_db)
) -> models.ServiceAccount:
    payload = decode_token(token)
    if not payload or payload.get("type") != "access":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    username = payload.get("sub")
    user = db.query(models.ServiceAccount).filter(
        models.ServiceAccount.name == username,
        models.ServiceAccount.is_active == True
    ).first()
    
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found or inactive",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return user


def require_role(required_roles: List[str]):
    def role_checker(current_user: models.ServiceAccount = Depends(get_current_user)) -> models.ServiceAccount:
        import json
        try:
            user_data = json.loads(current_user.token_hash)
            user_roles = user_data.get("roles", [])
        except Exception:
            user_roles = []
        
        if not any(role in user_roles for role in required_roles):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Required role(s): {required_roles}"
            )
        return current_user
    return role_checker

def get_current_user_from_token(
    token: str, 
    db: Session
) -> Optional[models.ServiceAccount]:
    """Get user from JWT token"""
    payload = decode_token(token)
    if not payload:
        return None
    
    if payload.get("type") != "access":
        return None
    
    username = payload.get("sub")
    if not username:
        return None
    
    user = db.query(models.ServiceAccount).filter(
        models.ServiceAccount.name == username,
        models.ServiceAccount.is_active == True
    ).first()
    
    return user

def create_test_user(db: Session, username: str = "testuser", roles: List[str] = None) -> models.ServiceAccount:
    """Create or get a test user for testing purposes (only works when TESTING=1)"""
    if os.getenv("TESTING") != "1":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Test login only available in testing mode"
        )
    
    if roles is None:
        roles = ["admin", "analyst", "viewer"]
    
    import json
    local_user = db.query(models.ServiceAccount).filter(
        models.ServiceAccount.name == username
    ).first()
    
    if not local_user:
        local_user = models.ServiceAccount(
            name=username,
            token_hash=json.dumps({"roles": roles, "ad_user": False, "test_user": True}),
            expires_at=datetime.utcnow() + timedelta(days=365),
            is_active=True,
        )
        db.add(local_user)
        db.commit()
        db.refresh(local_user)
    else:
        local_user.token_hash = json.dumps({"roles": roles, "ad_user": False, "test_user": True})
        local_user.is_active = True
        local_user.expires_at = datetime.utcnow() + timedelta(days=365)
        db.commit()
        db.refresh(local_user)
    
    return local_user


def create_test_tokens(user: models.ServiceAccount, roles: List[str]) -> tuple:
    """Create access and refresh tokens for test user"""
    token_data = {
        "sub": user.name,
        "roles": roles,
        "user_id": user.id,
    }
    access_token = create_access_token(token_data)
    refresh_token = create_refresh_token(token_data)
    return access_token, refresh_token
