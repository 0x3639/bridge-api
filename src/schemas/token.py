from datetime import datetime
from typing import Optional
from uuid import UUID

from pydantic import BaseModel


class TokenInfo(BaseModel):
    """Token information without the actual token value."""

    id: UUID
    user_id: UUID
    name: str
    expires_at: Optional[datetime]
    is_revoked: bool
    last_used_at: Optional[datetime]
    created_at: datetime

    class Config:
        from_attributes = True
