"""
Active Directory / LDAP Authentication Module
"""
import ldap3
from ldap3 import Server, Connection, ALL, SUBTREE, NTLM, SASL, KERBEROS
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
from pathlib import Path
from dotenv import load_dotenv
import bcrypt

load_dotenv(Path(__file__).parent.parent / ".env")

# JWT Settings
SECRET_KEY = os.getenv("JWT_SECRET_KEY", "your-secret-key-change-in-production")
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = int(os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES", "30"))
REFRESH_TOKEN_EXPIRE_DAYS = int(os.getenv("REFRESH_TOKEN_EXPIRE_DAYS", "7"))

# AD/LDAP Settings
AD_SERVER = os.getenv("AD_SERVER", "ldap://localhost:389")
AD_PORT = int(os.getenv("AD_PORT", "389"))
AD_DOMAIN = os.getenv("AD_DOMAIN", "EXAMPLE.COM")
AD_BASE_DN = os.getenv("AD_BASE_DN", "DC=example,DC=com")
AD_BIND_DN = os.getenv("AD_BIND_DN", "")
AD_BIND_PASSWORD = os.getenv("AD_BIND_PASSWORD", "")
AD_USE_SSL = os.getenv("AD_USE_SSL", "false").lower() == "true"
AD_SEARCH_FILTER = os.getenv("AD_SEARCH_FILTER", "(sAMAccountName={username})")
AD_GROUP_SEARCH_FILTER = os.getenv("AD_GROUP_SEARCH_FILTER", "(member={user_dn})")

# Role mapping from AD groups to application roles
# Loaded dynamically from .env (e.g., ROLE_ADMIN=G_GESIN_GOSD_OMIS)
def get_role_mapping() -> Dict[str, List[str]]:
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


def get_ad_connection() -> Connection:
    """Create and return an AD/LDAP connection"""
    try:
        server = Server(AD_SERVER, get_info=ALL, use_ssl=AD_USE_SSL)
        
        if AD_BIND_DN and AD_BIND_PASSWORD:
            # Service account bind
            conn = Connection(
                server,
                user=AD_BIND_DN,
                password=AD_BIND_PASSWORD,
                authentication=NTLM,
                auto_bind=True
            )
        else:
            # Anonymous bind (if allowed)
            conn = Connection(server, authentication=NTLM, auto_bind=True)
        
        return conn
    except LDAPException as e:
        raise ADAuthError(f"Failed to connect to AD: {str(e)}")


def authenticate_user(username: str, password: str) -> Optional[Dict[str, Any]]:
    """
    Authenticate a user against Active Directory.
    Returns user info dict if successful, None otherwise.
    """
    try:
        # Create connection for user authentication
        server = Server(AD_SERVER, get_info=ALL, use_ssl=AD_USE_SSL)
        
        # Try to bind with user credentials
        user_dn = f"{AD_DOMAIN}\\{username}"
        conn = Connection(
            server,
            user=user_dn,
            password=password,
            authentication=NTLM,
            auto_bind=True
        )
        
        if not conn.bound:
            return None
        
        # Search for user details
        search_filter = AD_SEARCH_FILTER.format(username=username)
        conn.search(
            search_base=AD_BASE_DN,
            search_filter=search_filter,
            search_scope=SUBTREE,
            attributes=[
                'sAMAccountName', 'displayName', 'mail', 'userPrincipalName',
                'memberOf', 'distinguishedName', 'givenName', 'sn'
            ]
        )
        
        if not conn.entries:
            return None
        
        entry = conn.entries[0]
        
        # Get user's groups
        groups = []
        if hasattr(entry, 'memberOf') and entry.memberOf:
            for group_dn in entry.memberOf.values:
                groups.append(str(group_dn))
        
        user_info = {
            "username": str(entry.sAMAccountName),
            "display_name": str(entry.displayName) if hasattr(entry, 'displayName') and entry.displayName else username,
            "email": str(entry.mail) if hasattr(entry, 'mail') and entry.mail else f"{username}@{AD_DOMAIN.lower()}",
            "user_principal_name": str(entry.userPrincipalName) if hasattr(entry, 'userPrincipalName') and entry.userPrincipalName else None,
            "distinguished_name": str(entry.distinguishedName) if hasattr(entry, 'distinguishedName') and entry.distinguishedName else None,
            "groups": groups,
            "given_name": str(entry.givenName) if hasattr(entry, 'givenName') and entry.givenName else None,
            "surname": str(entry.sn) if hasattr(entry, 'sn') and entry.sn else None,
        }
        
        conn.unbind()
        return user_info
        
    except LDAPException as e:
        raise ADAuthError(f"AD authentication failed: {str(e)}")


def get_user_groups(user_dn: str) -> List[str]:
    """Get all groups a user is member of (including nested groups)"""
    try:
        conn = get_ad_connection()
        
        # Search for groups where user is a member
        search_filter = AD_GROUP_SEARCH_FILTER.format(user_dn=user_dn)
        conn.search(
            search_base=AD_BASE_DN,
            search_filter=search_filter,
            search_scope=SUBTREE,
            attributes=['cn', 'distinguishedName']
        )
        
        groups = []
        for entry in conn.entries:
            groups.append(str(entry.cn))
        
        conn.unbind()
        return groups
    except LDAPException:
        return []


def map_ad_groups_to_roles(ad_groups: List[str]) -> List[str]:
    """Map AD groups to application roles"""
    roles = []
    role_map = get_role_mapping()
    
    for group in ad_groups:
        # Extract group CN for easier matching
        group_cn = group.split(',')[0].replace('CN=', '') if 'CN=' in group else group
        
        for role, groups in role_map.items():
            if any(g.lower() in group.lower() or g.lower() == group_cn.lower() for g in groups):
                roles.append(role)
    
    # Default role if no mapping found
    if not roles:
        roles = ["viewer"]
    
    return list(set(roles))  # Remove duplicates


def create_or_update_local_user(db: Session, ad_user: Dict[str, Any]) -> models.ServiceAccount:
    """Create or update local user record based on AD user info"""
    username = ad_user["username"]
    
    # Check if user exists locally
    local_user = db.query(models.ServiceAccount).filter(
        models.ServiceAccount.name == username
    ).first()
    
    # Map AD groups to roles
    roles = map_ad_groups_to_roles(ad_user.get("groups", []))
    
    if local_user:
        # Update existing user
        local_user.is_active = True
        local_user.expires_at = datetime.utcnow() + timedelta(days=365)
        # Store roles in token_hash field as JSON (or create a separate field)
        import json
        local_user.token_hash = json.dumps({"roles": roles, "ad_user": True})
    else:
        # Create new local user
        import json
        local_user = models.ServiceAccount(
            name=username,
            token_hash=json.dumps({"roles": roles, "ad_user": True}),
            expires_at=datetime.utcnow() + timedelta(days=365),
            is_active=True,
        )
        db.add(local_user)
    
    db.commit()
    db.refresh(local_user)
    return local_user


def create_access_token(data: dict, expires_delta: Optional[timedelta] = None) -> str:
    """Create JWT access token"""
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    to_encode.update({"exp": expire, "type": "access"})
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt


def create_refresh_token(data: dict) -> str:
    """Create JWT refresh token"""
    to_encode = data.copy()
    expire = datetime.utcnow() + timedelta(days=REFRESH_TOKEN_EXPIRE_DAYS)
    to_encode.update({"exp": expire, "type": "refresh"})
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt


def decode_token(token: str) -> Optional[dict]:
    """Decode and validate JWT token"""
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        return payload
    except jwt.ExpiredSignatureError:
        return None
    except jwt.JWTError:
        return None


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


# OAuth2 scheme for token extraction
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/auth/ad/login")


def get_current_user(
    token: str = Depends(oauth2_scheme),
    db: Session = Depends(get_db)
) -> models.ServiceAccount:
    """FastAPI dependency to get current authenticated user"""
    user = get_current_user_from_token(token, db)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return user


def require_role(required_roles: List[str]):
    """Dependency factory for role-based access control"""
    def role_checker(current_user: models.ServiceAccount = Depends(get_current_user)) -> models.ServiceAccount:
        import json
        try:
            user_data = json.loads(current_user.token_hash)
            user_roles = user_data.get("roles", [])
        except:
            user_roles = []
        
        if not any(role in user_roles for role in required_roles):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Required role(s): {required_roles}"
            )
        return current_user
    return role_checker


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