from datetime import datetime
from typing import TYPE_CHECKING, List, Optional

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String, Text, func
from sqlalchemy.dialects.postgresql import INET, JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.models.base import Base

if TYPE_CHECKING:
    from src.models.network_stats import NetworkStats


class OrchestratorNode(Base):
    """Orchestrator node configuration."""

    __tablename__ = "orchestrator_nodes"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(100), unique=True, nullable=False)
    ip_address: Mapped[str] = mapped_column(INET, nullable=False)
    pubkey: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    rpc_port: Mapped[int] = mapped_column(Integer, default=55000, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )

    # Relationships
    snapshots: Mapped[List["OrchestratorSnapshot"]] = relationship(
        "OrchestratorSnapshot",
        back_populates="node",
        cascade="all, delete-orphan",
    )

    def __repr__(self) -> str:
        return f"<OrchestratorNode(id={self.id}, name={self.name}, ip={self.ip_address})>"


class OrchestratorSnapshot(Base):
    """Point-in-time snapshot of orchestrator status."""

    __tablename__ = "orchestrator_snapshots"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    node_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("orchestrator_nodes.id"),
        nullable=False,
        index=True,
    )
    timestamp: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
        index=True,
    )
    pillar_name: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    producer_address: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    state: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    state_name: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    is_online: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    response_time_ms: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    error_message: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    raw_identity: Mapped[Optional[dict]] = mapped_column(JSONB, nullable=True)
    raw_status: Mapped[Optional[dict]] = mapped_column(JSONB, nullable=True)

    # Relationships
    node: Mapped["OrchestratorNode"] = relationship(
        "OrchestratorNode",
        back_populates="snapshots",
    )
    network_stats: Mapped[List["NetworkStats"]] = relationship(
        "NetworkStats",
        back_populates="snapshot",
        cascade="all, delete-orphan",
    )

    def __repr__(self) -> str:
        return f"<OrchestratorSnapshot(id={self.id}, node_id={self.node_id}, timestamp={self.timestamp})>"
