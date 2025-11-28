from typing import Optional
from uuid import UUID

from fastapi import APIRouter, Depends, Query
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.config import settings
from src.core.exceptions import NotFoundError, ValidationError
from src.core.security import hash_password
from src.dependencies import get_admin_user, get_db
from src.models.token import ApiToken
from src.models.user import User
from src.schemas.auth import TokenListResponse, TokenResponse
from src.schemas.user import (
    UserCreateRequest,
    UserListResponse,
    UserResponse,
    UserUpdateRequest,
)

router = APIRouter(prefix="/users", tags=["users"])


@router.get("", response_model=UserListResponse)
async def list_users(
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=100),
    is_active: Optional[bool] = None,
    _admin: User = Depends(get_admin_user),
    db: AsyncSession = Depends(get_db),
) -> UserListResponse:
    """List all users (admin only)."""
    query = select(User)

    if is_active is not None:
        query = query.where(User.is_active == is_active)

    # Get total count
    count_result = await db.execute(select(func.count()).select_from(query.subquery()))
    total = count_result.scalar_one()

    # Get users with pagination
    query = query.order_by(User.created_at.desc()).offset(skip).limit(limit)
    result = await db.execute(query)
    users = result.scalars().all()

    return UserListResponse(
        users=[UserResponse.model_validate(u) for u in users],
        total=total,
    )


@router.post("", response_model=UserResponse)
async def create_user(
    request: UserCreateRequest,
    _admin: User = Depends(get_admin_user),
    db: AsyncSession = Depends(get_db),
) -> UserResponse:
    """Create a new user (admin only)."""
    # Check for existing username or email
    existing = await db.execute(
        select(User).where(
            (User.username == request.username) | (User.email == request.email)
        )
    )
    if existing.scalar_one_or_none():
        raise ValidationError("Username or email already exists")

    # Set rate limits based on admin status
    rate_limit_per_second = request.rate_limit_per_second
    rate_limit_burst = request.rate_limit_burst

    if rate_limit_per_second is None:
        rate_limit_per_second = (
            settings.admin_rate_limit_per_second
            if request.is_admin
            else settings.default_rate_limit_per_second
        )
    if rate_limit_burst is None:
        rate_limit_burst = (
            settings.admin_rate_limit_burst
            if request.is_admin
            else settings.default_rate_limit_burst
        )

    user = User(
        username=request.username,
        email=request.email,
        password_hash=hash_password(request.password),
        is_admin=request.is_admin,
        rate_limit_per_second=rate_limit_per_second,
        rate_limit_burst=rate_limit_burst,
    )

    db.add(user)
    await db.commit()
    await db.refresh(user)

    return UserResponse.model_validate(user)


@router.get("/{user_id}", response_model=UserResponse)
async def get_user(
    user_id: UUID,
    _admin: User = Depends(get_admin_user),
    db: AsyncSession = Depends(get_db),
) -> UserResponse:
    """Get a user by ID (admin only)."""
    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()

    if user is None:
        raise NotFoundError("User not found")

    return UserResponse.model_validate(user)


@router.patch("/{user_id}", response_model=UserResponse)
async def update_user(
    user_id: UUID,
    request: UserUpdateRequest,
    _admin: User = Depends(get_admin_user),
    db: AsyncSession = Depends(get_db),
) -> UserResponse:
    """Update a user (admin only)."""
    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()

    if user is None:
        raise NotFoundError("User not found")

    # Update fields if provided
    if request.username is not None:
        # Check for duplicate username
        existing = await db.execute(
            select(User).where(User.username == request.username, User.id != user_id)
        )
        if existing.scalar_one_or_none():
            raise ValidationError("Username already exists")
        user.username = request.username

    if request.email is not None:
        # Check for duplicate email
        existing = await db.execute(
            select(User).where(User.email == request.email, User.id != user_id)
        )
        if existing.scalar_one_or_none():
            raise ValidationError("Email already exists")
        user.email = request.email

    if request.password is not None:
        user.password_hash = hash_password(request.password)

    if request.is_active is not None:
        user.is_active = request.is_active

    if request.is_admin is not None:
        user.is_admin = request.is_admin

    if request.rate_limit_per_second is not None:
        user.rate_limit_per_second = request.rate_limit_per_second

    if request.rate_limit_burst is not None:
        user.rate_limit_burst = request.rate_limit_burst

    await db.commit()
    await db.refresh(user)

    return UserResponse.model_validate(user)


@router.delete("/{user_id}")
async def deactivate_user(
    user_id: UUID,
    _admin: User = Depends(get_admin_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Deactivate a user (admin only). Does not delete the user."""
    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()

    if user is None:
        raise NotFoundError("User not found")

    user.is_active = False
    await db.commit()

    return {"status": "success", "message": "User deactivated"}


@router.get("/{user_id}/tokens", response_model=TokenListResponse)
async def list_user_tokens(
    user_id: UUID,
    _admin: User = Depends(get_admin_user),
    db: AsyncSession = Depends(get_db),
) -> TokenListResponse:
    """List all tokens for a specific user (admin only)."""
    # Verify user exists
    user_result = await db.execute(select(User).where(User.id == user_id))
    if user_result.scalar_one_or_none() is None:
        raise NotFoundError("User not found")

    result = await db.execute(
        select(ApiToken)
        .where(ApiToken.user_id == user_id)
        .order_by(ApiToken.created_at.desc())
    )
    tokens = result.scalars().all()

    return TokenListResponse(
        tokens=[TokenResponse.model_validate(t) for t in tokens],
        total=len(tokens),
    )


@router.delete("/{user_id}/tokens/{token_id}")
async def revoke_user_token(
    user_id: UUID,
    token_id: UUID,
    _admin: User = Depends(get_admin_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Revoke a specific token for a user (admin only)."""
    result = await db.execute(
        select(ApiToken).where(
            ApiToken.id == token_id,
            ApiToken.user_id == user_id,
        )
    )
    token = result.scalar_one_or_none()

    if token is None:
        raise NotFoundError("Token not found")

    token.is_revoked = True
    await db.commit()

    return {"status": "success", "message": "Token revoked"}
