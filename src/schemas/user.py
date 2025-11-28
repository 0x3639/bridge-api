from datetime import datetime
from typing import Optional
from uuid import UUID

from pydantic import BaseModel, EmailStr, Field


class UserCreateRequest(BaseModel):
    """Request body for creating a user (admin only)."""

    username: str = Field(..., min_length=3, max_length=50)
    email: EmailStr
    password: str = Field(..., min_length=8)
    is_admin: bool = False
    rate_limit_per_second: Optional[int] = None  # None = use default
    rate_limit_burst: Optional[int] = None  # None = use default


class UserUpdateRequest(BaseModel):
    """Request body for updating a user (admin only)."""

    username: Optional[str] = Field(None, min_length=3, max_length=50)
    email: Optional[EmailStr] = None
    password: Optional[str] = Field(None, min_length=8)
    is_active: Optional[bool] = None
    is_admin: Optional[bool] = None
    rate_limit_per_second: Optional[int] = None
    rate_limit_burst: Optional[int] = None


class UserResponse(BaseModel):
    """Response body for user info."""

    id: UUID
    username: str
    email: str
    is_active: bool
    is_admin: bool
    rate_limit_per_second: int
    rate_limit_burst: int
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class UserListResponse(BaseModel):
    """Response body for listing users."""

    users: list[UserResponse]
    total: int
