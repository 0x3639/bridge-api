from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel, Field


class WrapTokenResponse(BaseModel):
    """Response schema for a wrap token request."""

    request_id: str
    network_class: int
    chain_id: int
    to_address: str
    token_standard: str
    token_address: str
    token_symbol: str
    token_decimals: int
    amount: str  # String to preserve precision for large numbers
    fee: str  # String to preserve precision
    signature: str
    creation_momentum_height: int
    confirmations_to_finality: int
    created_at: datetime

    class Config:
        from_attributes = True


class UnwrapTokenResponse(BaseModel):
    """Response schema for an unwrap token request."""

    transaction_hash: str
    log_index: int
    registration_momentum_height: int
    network_class: int
    chain_id: int
    to_address: str
    token_address: str
    token_standard: str
    token_symbol: str
    token_decimals: int
    amount: str  # String to preserve precision
    signature: str
    redeemed: bool
    revoked: bool
    redeemable_in: int
    created_at: datetime

    class Config:
        from_attributes = True


class WrapTokenListResponse(BaseModel):
    """Paginated list of wrap token requests."""

    count: int
    page: int
    page_size: int
    items: List[WrapTokenResponse]


class UnwrapTokenListResponse(BaseModel):
    """Paginated list of unwrap token requests."""

    count: int
    page: int
    page_size: int
    items: List[UnwrapTokenResponse]


class BridgeSyncStatusResponse(BaseModel):
    """Status of the bridge data sync."""

    sync_complete: bool
    wrap_count: Optional[int] = None
    unwrap_count: Optional[int] = None
