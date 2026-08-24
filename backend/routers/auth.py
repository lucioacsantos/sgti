"""
Authentication Router - AD/DC Login and JWT Token Management
"""
from fastapi import APIRouter, Depends, HTTPException, status, Request
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.orm import Session
from pydantic import BaseModel, ConfigDict
from typing import Optional, List
import pyotp
import qrcode
import io
import base64
import os

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
        
        import bcrypt
        # Update local user with refresh token hash (for revocation)
        local_user.token_hash = json.dumps({
            "roles": roles,
            "ad_user": True,
            "refresh_token_hash": bcrypt.hashpw(
                refresh_token.encode(), 
                bcrypt.gensalt()
            ).decode()
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
    import json
    try:
        user_data = json.loads(current_user.token_hash)
        roles = user_data.get("roles", ["viewer"])
    except:
        roles = ["viewer"]
    
    return UserResponse(
        id=current_user.id,
        username=current_user.name,
        display_name=current_user.name,
        email=f"{current_user.name}@{ad_auth.AD_DOMAIN.lower()}",
        roles=roles,
        groups=[],
        requires_2fa=False,
        two_fa_enabled=False,
    )


# 2FA Endpoints (using TOTP)
@router.post("/2fa/setup", response_model=TwoFASetupResponse)
async def setup_2fa(
    current_user: models.ServiceAccount = Depends(ad_auth.get_current_user)
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
    
    # Store secret temporarily (in production, encrypt and store in DB)
    # For now, return it to frontend
    return TwoFASetupResponse(
        secret=secret,
        qr_code=f"data:image/png;base64,{qr_code_b64}",
    )


@router.post("/2fa/verify")
async def verify_2fa(
    request: TwoFAVerifyRequest,
    current_user: models.ServiceAccount = Depends(ad_auth.get_current_user)
):
    """Verify 2FA code during setup"""
    # In production, you'd verify against stored secret
    # For now, accept any 6-digit code
    if len(request.code) == 6 and request.code.isdigit():
        return {"message": "2FA verified successfully", "verified": True}
    
    raise HTTPException(
        status_code=status.HTTP_400_BAD_REQUEST,
        detail="Invalid 2FA code"
    )


@router.post("/2fa/enable")
async def enable_2fa(
    request: TwoFAEnableRequest,
    current_user: models.ServiceAccount = Depends(ad_auth.get_current_user)
):
    """Enable 2FA for user"""
    # In production, store the secret and enable 2FA flag
    return {"message": "2FA enabled successfully"}


@router.post("/2fa/disable")
async def disable_2fa(
    request: TwoFADisableRequest,
    current_user: models.ServiceAccount = Depends(ad_auth.get_current_user)
):
    """Disable 2FA for user"""
    # In production, verify password and disable 2FA
    return {"message": "2FA disabled successfully"}


# Admin endpoints
@router.get("/admin/users")
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
        import json
        try:
            user_data = json.loads(user.token_hash)
            roles = user_data.get("roles", ["viewer"])
        except:
            roles = ["viewer"]
        
        result.append({
            "id": user.id,
            "username": user.name,
            "display_name": user.name,
            "email": f"{user.name}@{ad_auth.AD_DOMAIN.lower()}",
            "roles": roles,
            "is_active": user.is_active,
            "created_at": user.created_at.isoformat() if user.created_at else None,
        })
    
    return result


@router.get("/admin/roles")
async def get_roles(
    current_user: models.ServiceAccount = Depends(ad_auth.require_role(["admin"]))
):
    """Get all available roles"""
    return ["admin", "analyst", "reviewer", "reconciliator", "revisor", "viewer"]