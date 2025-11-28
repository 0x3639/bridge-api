from datetime import datetime
from ipaddress import IPv4Address, IPv6Address
from typing import Any, Optional, Union

from pydantic import BaseModel, field_validator


class NetworkStatsResponse(BaseModel):
    """Network statistics for a single network."""

    network: str
    wraps_count: int
    unwraps_count: int


class OrchestratorNodeResponse(BaseModel):
    """Orchestrator node configuration info."""

    id: int
    name: str
    ip_address: str
    pubkey: Optional[str]
    rpc_port: int
    is_active: bool
    created_at: datetime

    @field_validator("ip_address", mode="before")
    @classmethod
    def convert_ip_to_string(cls, v: Any) -> str:
        """Convert IPv4Address/IPv6Address to string."""
        if isinstance(v, (IPv4Address, IPv6Address)):
            return str(v)
        return v

    class Config:
        from_attributes = True


class OrchestratorStatusResponse(BaseModel):
    """Current status of a single orchestrator."""

    node_id: int
    node_name: str
    ip_address: str
    pillar_name: Optional[str]
    producer_address: Optional[str]
    state: Optional[int]
    state_name: Optional[str]
    is_online: bool
    response_time_ms: Optional[int]
    error_message: Optional[str]
    network_stats: list[NetworkStatsResponse]
    last_checked: datetime


class BridgeStatusResponse(BaseModel):
    """Overall bridge status with all orchestrators."""

    timestamp: datetime
    bridge_status: str  # "online" or "offline"
    online_count: int
    total_count: int
    min_required: int
    orchestrators: list[OrchestratorStatusResponse]


class BridgeSummaryResponse(BaseModel):
    """Summary of bridge status without individual orchestrator details."""

    timestamp: datetime
    bridge_status: str
    online_count: int
    total_count: int
    min_required: int


class OrchestratorHistoryResponse(BaseModel):
    """Historical snapshot of an orchestrator."""

    id: int
    timestamp: datetime
    pillar_name: Optional[str]
    producer_address: Optional[str]
    state: Optional[int]
    state_name: Optional[str]
    is_online: bool
    response_time_ms: Optional[int]
    error_message: Optional[str]
    network_stats: list[NetworkStatsResponse]

    class Config:
        from_attributes = True


class OrchestratorHistoryListResponse(BaseModel):
    """List of historical snapshots with pagination."""

    node_id: int
    node_name: str
    snapshots: list[OrchestratorHistoryResponse]
    total: int
    page: int
    page_size: int


class OrchestratorNodeListResponse(BaseModel):
    """List of orchestrator nodes."""

    nodes: list[OrchestratorNodeResponse]
    total: int
