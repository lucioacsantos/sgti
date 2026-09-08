"""
Authentication Router - AD/DC Login and JWT Token Management
"""
from fastapi import APIRouter, Depends, HTTPException, status, Request
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.orm import Session
from pydantic import BaseModel, ConfigDict
from typing import Optional, List
from datetime import datetime, timedelta, timezone
import pyotp
import qrcode
import io
import base64
import os
import secrets

from database import get_db
import models
import ad_auth
from ad_auth import (
    authenticate_user, create_or_update_local_user, create_access_token,
    create_refresh_token, decode_token, get_current_user_from_token,
    ADAuthError, create_test_user, create_test_tokens
)


router = APIRouter(prefix="/auth", tags=["Authentication"])


# Request/Response Models
class ADLoginRequest(BaseModel):
    username: str
    password: str


class TokenResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    user: dict
    requires_2fa: bool = False


class TwoFASetupResponse(BaseModel):
    secret: str
    qr_code: str
    issuer: str = "SGTI CMDB"


class TwoFAVerifyRequest(BaseModel):
    code: str


class TwoFAEnableRequest(BaseModel):
    code: str


class TwoFADisableRequest(BaseModel):
    password: str


class RefreshTokenRequest(BaseModel):
    refresh_token: str


class TestLoginRequest(BaseModel):
    username: str = "testuser"
    roles: Optional[List[str]] = None


class UserResponse(BaseModel):
    id: int
    username: str
    display_name: str
    email: str
    roles: list
    groups: list
    requires_2fa: bool
    two_fa_enabled: bool

    model_config = ConfigDict(from_attributes=True)


class AdminUserOut(BaseModel):
    id: int
    username: str
    display_name: str
    email: str
    roles: list
    is_active: bool
    is_service_account: bool
    two_fa_enabled: bool
    created_at: Optional[str] = None
    expires_at: Optional[str] = None


class AdminUserUpdate(BaseModel):
    is_active: Optional[bool] = None
    roles: Optional[List[str]] = None
    expires_at: Optional[datetime] = None


class ServiceTokenCreate(BaseModel):
    name: str
    expires_at: Optional[datetime] = None


class ServiceTokenOut(BaseModel):
    id: int
    name: str
    is_active: bool
    created_at: Optional[str] = None
    expires_at: Optional[str] = None
    token: Optional[str] = None


@router.post("/ad/login", response_model=TokenResponse)
async def ad_login(
    request: ADLoginRequest,
    db: Session = Depends(get_db)
):
    """
    Authenticate user against Active Directory.
    Returns JWT tokens if successful.
    """
    try:
        # Authenticate against AD
        ad_user = authenticate_user(request.username, request.password)
        
        if not ad_user:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid username or password",
                headers={"WWW-Authenticate": "Bearer"},
            )
        
        # Create or update local user record
        local_user = create_or_update_local_user(db, ad_user)
        
        # Get user roles from local storage
        import json
        try:
            user_data = json.loads(local_user.token_hash)
            roles = user_data.get("roles", ["viewer"])
        except:
            roles = ["viewer"]
        
        # Check if 2FA is required
        requires_2fa = False
        two_fa_enabled = False
        
        # Create tokens
        token_data = {
            "sub": local_user.name,
            "roles": roles,
            "user_id": local_user.id,
        }
        
        access_token = create_access_token(token_data)
        refresh_token = create_refresh_token(token_data)
        
        import hashlib

        # Gera hash SHA-256 do refresh token
        refresh_token_hash = hashlib.sha256(refresh_token.encode('utf-8')).hexdigest()

        # Atualiza o local_user
        local_user.token_hash = json.dumps({
            "roles": roles,
            "ad_user": True,
            "refresh_token_hash": refresh_token_hash
        })
        db.commit()
        
        return TokenResponse(
            access_token=access_token,
            refresh_token=refresh_token,
            user={
                "id": local_user.id,
                "username": ad_user["username"],
                "display_name": ad_user["display_name"],
                "email": ad_user["email"],
                "roles": roles,
                "groups": ad_user.get("groups", []),
            },
            requires_2fa=requires_2fa,
        )
        
    except ADAuthError as e:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"Authentication service unavailable: {str(e)}"
        )


@router.post("/test/login", response_model=TokenResponse)
async def test_login(
    request: TestLoginRequest,
    db: Session = Depends(get_db)
):
    """
    Test login endpoint - only works when TESTING=1 environment variable is set.
    Creates a test user with specified roles and returns JWT tokens.
    """
    if os.getenv("TESTING") != "1":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Test login only available in testing mode"
        )
    
    try:
        # Create or get test user
        local_user = create_test_user(db, request.username, request.roles)
        
        # Get roles
        import json
        try:
            user_data = json.loads(local_user.token_hash)
            roles = user_data.get("roles", ["viewer"])
        except:
            roles = ["viewer"]
        
        # Create tokens
        access_token, refresh_token = create_test_tokens(local_user, roles)
        
        return TokenResponse(
            access_token=access_token,
            refresh_token=refresh_token,
            user={
                "id": local_user.id,
                "username": local_user.name,
                "display_name": f"Test User ({local_user.name})",
                "email": f"{local_user.name}@test.local",
                "roles": roles,
                "groups": [],
            },
            requires_2fa=False,
        )
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Test login failed: {str(e)}"
        )


@router.post("/refresh", response_model=TokenResponse)
async def refresh_token(
    request: RefreshTokenRequest,
    db: Session = Depends(get_db)
):
    """Refresh access token using refresh token"""
    payload = decode_token(request.refresh_token)
    
    if not payload or payload.get("type") != "refresh":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid refresh token"
        )
    
    username = payload.get("sub")
    user = db.query(models.ServiceAccount).filter(
        models.ServiceAccount.name == username,
        models.ServiceAccount.is_active == True
    ).first()
    
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found or inactive"
        )
    
    # Get roles
    import json
    try:
        user_data = json.loads(user.token_hash)
        roles = user_data.get("roles", ["viewer"])
    except:
        roles = ["viewer"]
    
    token_data = {
        "sub": user.name,
        "roles": roles,
        "user_id": user.id,
    }
    
    access_token = create_access_token(token_data)
    new_refresh_token = create_refresh_token(token_data)
    
    return TokenResponse(
        access_token=access_token,
        refresh_token=new_refresh_token,
        user={
            "id": user.id,
            "username": user.name,
            "display_name": user.name,
            "email": f"{user.name}@{ad_auth.AD_DOMAIN.lower()}",
            "roles": roles,
            "groups": [],
        },
        requires_2fa=False,
    )


@router.post("/logout")
async def logout(
    request: RefreshTokenRequest,
    db: Session = Depends(get_db)
):
    """Logout - invalidate refresh token"""
    # In a production system, you'd maintain a token blacklist
    # For now, we just return success
    return {"message": "Logged out successfully"}


@router.get("/me", response_model=UserResponse)
async def get_current_user_info(
    current_user: models.ServiceAccount = Depends(ad_auth.get_current_user)
):
    """Get current user info from JWT token"""
    roles = _read_roles(current_user)

    return UserResponse(
        id=current_user.id,
        username=current_user.name,
        display_name=current_user.name,
        email=_user_email(current_user),
        roles=roles,
        groups=[],
        requires_2fa=False,
        two_fa_enabled=bool(current_user.totp_enabled),
    )


# 2FA Endpoints (using TOTP)
@router.post("/2fa/setup", response_model=TwoFASetupResponse)
async def setup_2fa(
    current_user: models.ServiceAccount = Depends(ad_auth.get_current_user),
    db: Session = Depends(get_db)
):
    """Generate 2FA secret and QR code for authenticator app"""
    # Generate secret
    secret = pyotp.random_base32()

    # Create TOTP URI
    totp = pyotp.TOTP(secret)
    provisioning_uri = totp.provisioning_uri(
        name=current_user.name,
        issuer_name="SGTI CMDB"
    )

    # Generate QR code
    qr = qrcode.QRCode(version=1, box_size=10, border=5)
    qr.add_data(provisioning_uri)
    qr.make(fit=True)
    img = qr.make_image(fill_color="black", back_color="white")

    # Convert to base64
    buffered = io.BytesIO()
    img.save(buffered, format="PNG")
    qr_code_b64 = base64.b64encode(buffered.getvalue()).decode()

    # Persist secret (not yet enabled; activated after verify)
    current_user.totp_secret = secret
    db.commit()

    return TwoFASetupResponse(
        secret=secret,
        qr_code=f"data:image/png;base64,{qr_code_b64}",
    )


@router.post("/2fa/verify")
async def verify_2fa(
    request: TwoFAVerifyRequest,
    current_user: models.ServiceAccount = Depends(ad_auth.get_current_user),
    db: Session = Depends(get_db)
):
    """Verify 2FA code during setup and enable 2FA"""
    if not current_user.totp_secret:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Nenhum setup de 2FA pendente. Solicite um novo QR Code."
        )

    totp = pyotp.TOTP(current_user.totp_secret)
    if not totp.verify(request.code, valid_window=1):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Código 2FA inválido."
        )

    current_user.totp_enabled = True
    db.commit()
    return {"message": "2FA habilitado com sucesso", "verified": True}


@router.post("/2fa/enable")
async def enable_2fa(
    request: TwoFAEnableRequest,
    current_user: models.ServiceAccount = Depends(ad_auth.get_current_user),
    db: Session = Depends(get_db)
):
    """Enable 2FA for user (alias for verify with code confirmation)"""
    if not current_user.totp_secret:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Solicite um setup de 2FA antes de habilitar."
        )

    totp = pyotp.TOTP(current_user.totp_secret)
    if not totp.verify(request.code, valid_window=1):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Código 2FA inválido."
        )

    current_user.totp_enabled = True
    db.commit()
    return {"message": "2FA habilitado com sucesso"}


@router.post("/2fa/disable")
async def disable_2fa(
    request: TwoFADisableRequest,
    current_user: models.ServiceAccount = Depends(ad_auth.get_current_user),
    db: Session = Depends(get_db)
):
    """Disable 2FA for user (requires password confirmation)"""
    try:
        ad_user = authenticate_user(current_user.name, request.password)
        if not ad_user:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Senha inválida."
            )
    except ADAuthError as e:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"Serviço de autenticação indisponível: {str(e)}"
        )

    current_user.totp_enabled = False
    current_user.totp_secret = None
    db.commit()
    return {"message": "2FA desabilitado com sucesso"}


# Admin endpoints
@router.get("/admin/users", response_model=List[AdminUserOut])
async def list_users(
    skip: int = 0,
    limit: int = 100,
    db: Session = Depends(get_db),
    current_user: models.ServiceAccount = Depends(ad_auth.require_role(["admin"]))
):
    """List all users (admin only)"""
    users = db.query(models.ServiceAccount).offset(skip).limit(limit).all()

    result = []
    for user in users:
        roles = _read_roles(user)
        is_ad_user = _is_ad_user(user)
        email = _user_email(user)
        result.append(AdminUserOut(
            id=user.id,
            username=user.name,
            display_name=user.name,
            email=email,
            roles=roles,
            is_active=user.is_active,
            is_service_account=not is_ad_user,
            two_fa_enabled=bool(user.totp_enabled),
            created_at=user.created_at.isoformat() if user.created_at else None,
            expires_at=user.expires_at.isoformat() if user.expires_at else None,
        ))

    return result


@router.patch("/admin/users/{user_id}", response_model=AdminUserOut)
async def update_user(
    user_id: int,
    payload: AdminUserUpdate,
    db: Session = Depends(get_db),
    current_user: models.ServiceAccount = Depends(ad_auth.require_role(["admin"]))
):
    """Activate/deactivate a user account (admin only)"""
    import json

    user = db.query(models.ServiceAccount).filter(
        models.ServiceAccount.id == user_id
    ).first()
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Usuário não encontrado")

    if payload.is_active is not None:
        user.is_active = payload.is_active

    if payload.roles is not None:
        try:
            user_data = json.loads(user.token_hash)
        except Exception:
            user_data = {}
        user_data["roles"] = payload.roles
        user.token_hash = json.dumps(user_data)

    if payload.expires_at is not None:
        user.expires_at = payload.expires_at

    db.commit()
    db.refresh(user)

    roles = _read_roles(user)
    is_ad_user = _is_ad_user(user)
    return AdminUserOut(
        id=user.id,
        username=user.name,
        display_name=user.name,
        email=_user_email(user),
        roles=roles,
        is_active=user.is_active,
        is_service_account=not is_ad_user,
        two_fa_enabled=bool(user.totp_enabled),
        created_at=user.created_at.isoformat() if user.created_at else None,
        expires_at=user.expires_at.isoformat() if user.expires_at else None,
    )


@router.post("/admin/users/{user_id}/2fa/disable")
async def admin_disable_2fa(
    user_id: int,
    db: Session = Depends(get_db),
    current_user: models.ServiceAccount = Depends(ad_auth.require_role(["admin"]))
):
    """Disable 2FA for a user (admin only)"""
    user = db.query(models.ServiceAccount).filter(
        models.ServiceAccount.id == user_id
    ).first()
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Usuário não encontrado")

    if not user.totp_enabled:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="2FA já está desabilitado para este usuário")

    user.totp_enabled = False
    user.totp_secret = None
    db.commit()
    return {"message": f"2FA desabilitado para o usuário {user.name}"}


@router.get("/admin/tokens", response_model=List[ServiceTokenOut])
async def list_service_tokens(
    db: Session = Depends(get_db),
    current_user: models.ServiceAccount = Depends(ad_auth.require_role(["admin"]))
):
    """List service tokens (automation accounts) — admin only"""
    accounts = db.query(models.ServiceAccount).all()
    result = []
    for acc in accounts:
        if _is_ad_user(acc):
            continue
        result.append(ServiceTokenOut(
            id=acc.id,
            name=acc.name,
            is_active=acc.is_active,
            created_at=acc.created_at.isoformat() if acc.created_at else None,
            expires_at=acc.expires_at.isoformat() if acc.expires_at else None,
        ))
    return result


@router.post("/admin/tokens", response_model=ServiceTokenOut, status_code=201)
async def create_service_token(
    payload: ServiceTokenCreate,
    db: Session = Depends(get_db),
    current_user: models.ServiceAccount = Depends(ad_auth.require_role(["admin"]))
):
    """Create a service token (automation account) — admin only. Token plaintext shown once."""
    existing = db.query(models.ServiceAccount).filter(
        models.ServiceAccount.name == payload.name
    ).first()
    if existing:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=f"Já existe uma conta com o nome '{payload.name}'")

    token = secrets.token_urlsafe(43)
    expires_at = payload.expires_at or (datetime.now(timezone.utc) + timedelta(days=365))

    account = models.ServiceAccount(
        name=payload.name,
        expires_at=expires_at,
        is_active=True,
    )
    account.set_token(token)
    db.add(account)
    db.commit()
    db.refresh(account)

    return ServiceTokenOut(
        id=account.id,
        name=account.name,
        is_active=account.is_active,
        created_at=account.created_at.isoformat() if account.created_at else None,
        expires_at=account.expires_at.isoformat() if account.expires_at else None,
        token=token,
    )


@router.delete("/admin/tokens/{account_id}", status_code=204)
async def delete_service_token(
    account_id: int,
    db: Session = Depends(get_db),
    current_user: models.ServiceAccount = Depends(ad_auth.require_role(["admin"]))
):
    """Delete a service token (automation account) — admin only"""
    account = db.query(models.ServiceAccount).filter(
        models.ServiceAccount.id == account_id
    ).first()
    if not account:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Token de serviço não encontrado")

    if _is_ad_user(account):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Não é possível excluir uma conta de usuário AD via tokens")

    db.delete(account)
    db.commit()
    return None


@router.get("/admin/roles")
async def get_roles(
    current_user: models.ServiceAccount = Depends(ad_auth.require_role(["admin"]))
):
    """Get all available roles"""
    return ["admin", "analyst", "reviewer", "reconciliator", "revisor", "viewer"]


def _read_roles(user: models.ServiceAccount) -> list:
    import json
    try:
        user_data = json.loads(user.token_hash)
        return user_data.get("roles", ["viewer"])
    except Exception:
        return ["viewer"]


def _is_ad_user(user: models.ServiceAccount) -> bool:
    """AD users store roles JSON in token_hash; service tokens store bcrypt hashes."""
    import json
    try:
        user_data = json.loads(user.token_hash)
        return isinstance(user_data, dict) and user_data.get("ad_user") is True
    except Exception:
        return False


def _user_email(user: models.ServiceAccount) -> str:
    import json
    try:
        user_data = json.loads(user.token_hash)
        email = user_data.get("email")
        if email:
            return email
    except Exception:
        pass
    return f"{user.name}@{ad_auth.AD_DOMAIN.lower()}"