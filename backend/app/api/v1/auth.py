from typing import Optional
from fastapi import APIRouter, Cookie, Depends, Header, HTTPException, Request, Response, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user, get_db
from app.core.config import settings
from app.models.user import User
from app.schemas.auth import (
    MessageResponse,
    RefreshTokenRequest,
    TokenResponse,
    UserLoginRequest,
    UserRegisterRequest,
    UserResponse,
)
from app.services.auth.service import AuthService

router = APIRouter(prefix="/auth", tags=["Authentication"])


@router.post("/register", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
async def register(
    request: UserRegisterRequest,
    db: AsyncSession = Depends(get_db),
):
    """Register a new participant account with unique username and email."""
    try:
        user = await AuthService.register_user(
            db=db,
            username=request.username,
            email=request.email,
            password=request.password,
            full_name=request.full_name,
        )
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))

    roles = [ur.role.name for ur in user.user_roles if ur.role]
    return UserResponse(
        id=user.id,
        username=user.username,
        email=user.email,
        full_name=user.full_name,
        roles=roles,
        email_verified=user.email_verified,
        account_status=user.account_status,
        avatar_url=user.avatar_url,
        created_at=user.created_at,
    )


@router.post("/login", response_model=TokenResponse)
async def login(
    request: UserLoginRequest,
    response: Response,
    req: Request,
    db: AsyncSession = Depends(get_db),
):
    """Authenticate with username/email and password, receiving JWT access and refresh tokens."""
    try:
        user = await AuthService.authenticate_user(
            db=db,
            username_or_email=request.username_or_email,
            password=request.password,
        )
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(e))

    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid credentials",
            headers={"WWW-Authenticate": "Bearer"},
        )

    device_metadata = {
        "user_agent": req.headers.get("user-agent", "unknown"),
        "client_ip": req.client.host if req.client else "unknown",
    }

    access_token, refresh_token, expires_in = await AuthService.create_tokens_for_user(
        db=db,
        user=user,
        device_metadata=device_metadata,
    )

    # Set optional HttpOnly refresh cookie
    response.set_cookie(
        key="refresh_token",
        value=refresh_token,
        httponly=True,
        secure=settings.COOKIE_SECURE,
        samesite="lax",
        max_age=settings.REFRESH_TOKEN_EXPIRE_DAYS * 86400,
        path="/api/v1/auth",
    )

    return TokenResponse(
        access_token=access_token,
        refresh_token=refresh_token,
        token_type="bearer",
        expires_in=expires_in,
    )


@router.post("/refresh", response_model=TokenResponse)
async def refresh_token(
    response: Response,
    req: Request,
    body: Optional[RefreshTokenRequest] = None,
    refresh_token_cookie: Optional[str] = Cookie(None, alias="refresh_token"),
    db: AsyncSession = Depends(get_db),
):
    """Rotate an existing refresh token and issue a new access token and refresh token."""
    raw_token = None
    if body and body.refresh_token:
        raw_token = body.refresh_token
    elif refresh_token_cookie:
        raw_token = refresh_token_cookie

    if not raw_token:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Refresh token required in request body or cookie",
        )

    device_metadata = {
        "user_agent": req.headers.get("user-agent", "unknown"),
        "client_ip": req.client.host if req.client else "unknown",
    }

    try:
        new_access, new_refresh, expires_in = await AuthService.rotate_refresh_token(
            db=db,
            raw_refresh_token=raw_token,
            device_metadata=device_metadata,
        )
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=str(e))

    response.set_cookie(
        key="refresh_token",
        value=new_refresh,
        httponly=True,
        secure=settings.COOKIE_SECURE,
        samesite="lax",
        max_age=settings.REFRESH_TOKEN_EXPIRE_DAYS * 86400,
        path="/api/v1/auth",
    )

    return TokenResponse(
        access_token=new_access,
        refresh_token=new_refresh,
        token_type="bearer",
        expires_in=expires_in,
    )


@router.post("/logout", response_model=MessageResponse)
async def logout(
    response: Response,
    body: Optional[RefreshTokenRequest] = None,
    refresh_token_cookie: Optional[str] = Cookie(None, alias="refresh_token"),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Revoke refresh token and clear session cookies."""
    raw_token = None
    if body and body.refresh_token:
        raw_token = body.refresh_token
    elif refresh_token_cookie:
        raw_token = refresh_token_cookie

    if raw_token:
        await AuthService.revoke_refresh_token(db=db, raw_refresh_token=raw_token)

    response.delete_cookie(key="refresh_token", path="/api/v1/auth")
    return MessageResponse(message="Successfully logged out")


@router.get("/me", response_model=UserResponse)
async def get_me(
    current_user: User = Depends(get_current_user),
):
    """Retrieve profile and roles of currently authenticated user."""
    roles = [ur.role.name for ur in current_user.user_roles if ur.role]
    return UserResponse(
        id=current_user.id,
        username=current_user.username,
        email=current_user.email,
        full_name=current_user.full_name,
        roles=roles,
        email_verified=current_user.email_verified,
        account_status=current_user.account_status,
        avatar_url=current_user.avatar_url,
        created_at=current_user.created_at,
    )
