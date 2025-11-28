from datetime import datetime, timezone
from uuid import UUID

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.config import settings
from src.core.exceptions import AuthenticationError, NotFoundError
from src.core.security import (
    create_session_jwt,
    generate_api_token,
    hash_password,
    verify_password,
)
from src.dependencies import get_current_active_user, get_db
from src.models.token import ApiToken
from src.models.user import User
from src.schemas.auth import (
    CurrentUserResponse,
    LoginRequest,
    LoginResponse,
    TokenCreateRequest,
    TokenCreateResponse,
    TokenListResponse,
    TokenResponse,
)

router = APIRouter(prefix="/auth", tags=["authentication"])


@router.post("/login", response_model=LoginResponse)
async def login(
    request: LoginRequest,
    db: AsyncSession = Depends(get_db),
) -> LoginResponse:
    """
    Authenticate with username/password and receive a session JWT.

    The JWT can be used to create API tokens or access the API temporarily.
    """
    # Find user by username
    result = await db.execute(select(User).where(User.username == request.username))
    user = result.scalar_one_or_none()

    if user is None or not verify_password(request.password, user.password_hash):
        raise AuthenticationError("Invalid username or password")

    if not user.is_active:
        raise AuthenticationError("User account is disabled")

    # Create session JWT
    access_token = create_session_jwt(str(user.id))

    return LoginResponse(
        access_token=access_token,
        token_type="bearer",
        expires_in=settings.access_token_expire_minutes * 60,
    )


@router.post("/tokens", response_model=TokenCreateResponse)
async def create_token(
    request: TokenCreateRequest,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
) -> TokenCreateResponse:
    """
    Create a new API token for the authenticated user.

    The token is only shown once in this response. Store it securely.
    """
    # Generate token
    token, token_hash = generate_api_token()

    # Create token record
    api_token = ApiToken(
        user_id=current_user.id,
        token_hash=token_hash,
        name=request.name,
        expires_at=request.expires_at,
    )

    db.add(api_token)
    await db.commit()
    await db.refresh(api_token)

    return TokenCreateResponse(
        id=api_token.id,
        name=api_token.name,
        token=token,  # Only returned once
        expires_at=api_token.expires_at,
        created_at=api_token.created_at,
    )


@router.get("/tokens", response_model=TokenListResponse)
async def list_tokens(
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
) -> TokenListResponse:
    """List all API tokens for the authenticated user."""
    result = await db.execute(
        select(ApiToken)
        .where(ApiToken.user_id == current_user.id)
        .order_by(ApiToken.created_at.desc())
    )
    tokens = result.scalars().all()

    return TokenListResponse(
        tokens=[TokenResponse.model_validate(t) for t in tokens],
        total=len(tokens),
    )


@router.delete("/tokens/{token_id}")
async def revoke_token(
    token_id: UUID,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Revoke an API token."""
    result = await db.execute(
        select(ApiToken).where(
            ApiToken.id == token_id,
            ApiToken.user_id == current_user.id,
        )
    )
    token = result.scalar_one_or_none()

    if token is None:
        raise NotFoundError("Token not found")

    token.is_revoked = True
    await db.commit()

    return {"status": "success", "message": "Token revoked"}


@router.get("/me", response_model=CurrentUserResponse)
async def get_current_user_info(
    current_user: User = Depends(get_current_active_user),
) -> CurrentUserResponse:
    """Get information about the currently authenticated user."""
    return CurrentUserResponse.model_validate(current_user)
