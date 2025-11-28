from typing import TYPE_CHECKING

from sqlalchemy import ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.models.base import Base

if TYPE_CHECKING:
    from src.models.orchestrator import OrchestratorSnapshot


class NetworkStats(Base):
    """Network statistics for an orchestrator snapshot."""

    __tablename__ = "network_stats"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    snapshot_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("orchestrator_snapshots.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    network: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
    )  # 'bnb', 'eth', 'supernova'
    wraps_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    unwraps_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)

    # Relationships
    snapshot: Mapped["OrchestratorSnapshot"] = relationship(
        "OrchestratorSnapshot",
        back_populates="network_stats",
    )

    def __repr__(self) -> str:
        return f"<NetworkStats(id={self.id}, network={self.network}, wraps={self.wraps_count}, unwraps={self.unwraps_count})>"
