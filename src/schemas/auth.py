from datetime import datetime
from typing import Optional
from uuid import UUID

from pydantic import BaseModel, EmailStr, Field


class LoginRequest(BaseModel):
    """Request body for login endpoint."""

    username: str = Field(..., min_length=3, max_length=50)
    password: str = Field(..., min_length=8)


class LoginResponse(BaseModel):
    """Response body for login endpoint."""

    access_token: str
    token_type: str = "bearer"
    expires_in: int  # seconds


class TokenCreateRequest(BaseModel):
    """Request body for creating an API token."""

    name: str = Field(..., min_length=1, max_length=100)
    expires_at: Optional[datetime] = None  # None = never expires


class TokenCreateResponse(BaseModel):
    """Response body for token creation (token only shown once)."""

    id: UUID
    name: str
    token: str  # Only returned on creation
    expires_at: Optional[datetime]
    created_at: datetime


class TokenResponse(BaseModel):
    """Response body for token info (without the actual token)."""

    id: UUID
    name: str
    expires_at: Optional[datetime]
    is_revoked: bool
    last_used_at: Optional[datetime]
    created_at: datetime

    class Config:
        from_attributes = True


class TokenListResponse(BaseModel):
    """Response body for listing tokens."""

    tokens: list[TokenResponse]
    total: int


class CurrentUserResponse(BaseModel):
    """Response body for /auth/me endpoint."""

    id: UUID
    username: str
    email: str
    is_admin: bool
    is_active: bool
    rate_limit_per_second: int
    rate_limit_burst: int
    created_at: datetime

    class Config:
        from_attributes = True
