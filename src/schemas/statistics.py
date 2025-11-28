from datetime import datetime
from typing import Optional

from pydantic import BaseModel


class UptimeStats(BaseModel):
    """Uptime statistics for a node or the bridge."""

    node_id: Optional[int] = None
    node_name: Optional[str] = None
    period_start: datetime
    period_end: datetime
    total_snapshots: int
    online_snapshots: int
    uptime_percentage: float


class NetworkAggregateStats(BaseModel):
    """Aggregate network statistics."""

    network: str
    total_wraps: int
    total_unwraps: int
    period_start: datetime
    period_end: datetime


class BridgeHealthOverTime(BaseModel):
    """Bridge health data point."""

    timestamp: datetime
    online_count: int
    total_count: int
    is_bridge_online: bool


class BridgeHealthResponse(BaseModel):
    """Historical bridge health data."""

    period_start: datetime
    period_end: datetime
    data_points: list[BridgeHealthOverTime]
    avg_online_count: float
    min_online_count: int
    max_online_count: int


class NetworkStatsResponse(BaseModel):
    """Network statistics over a time period."""

    period_start: datetime
    period_end: datetime
    networks: list[NetworkAggregateStats]


class UptimeResponse(BaseModel):
    """Uptime statistics response."""

    period_start: datetime
    period_end: datetime
    bridge_uptime_percentage: float
    node_uptimes: list[UptimeStats]
