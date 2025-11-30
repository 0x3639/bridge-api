from datetime import datetime
from typing import Optional

from sqlalchemy import (
    BigInteger,
    Boolean,
    DateTime,
    Index,
    Integer,
    Numeric,
    String,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column

from src.models.base import Base


class WrapTokenRequest(Base):
    """Wrap token request from the bridge (Zenon -> Ethereum)."""

    __tablename__ = "wrap_token_requests"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    request_id: Mapped[str] = mapped_column(
        String(64), unique=True, nullable=False, index=True
    )
    network_class: Mapped[int] = mapped_column(Integer, nullable=False)
    chain_id: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    to_address: Mapped[str] = mapped_column(String(42), nullable=False, index=True)
    token_standard: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    token_address: Mapped[str] = mapped_column(String(42), nullable=False)
    token_symbol: Mapped[str] = mapped_column(String(20), nullable=False, index=True)
    token_decimals: Mapped[int] = mapped_column(Integer, nullable=False)
    amount: Mapped[int] = mapped_column(Numeric(78, 0), nullable=False)
    fee: Mapped[int] = mapped_column(Numeric(78, 0), nullable=False)
    signature: Mapped[str] = mapped_column(String(100), nullable=False)
    creation_momentum_height: Mapped[int] = mapped_column(
        BigInteger, nullable=False, index=True
    )
    confirmations_to_finality: Mapped[int] = mapped_column(Integer, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )

    __table_args__ = (
        Index(
            "ix_wrap_chain_token", "chain_id", "token_standard"
        ),
        Index(
            "ix_wrap_momentum_desc", creation_momentum_height.desc()
        ),
    )

    def __repr__(self) -> str:
        return f"<WrapTokenRequest(id={self.id}, request_id={self.request_id[:16]}..., amount={self.amount})>"


class UnwrapTokenRequest(Base):
    """Unwrap token request from the bridge (Ethereum -> Zenon)."""

    __tablename__ = "unwrap_token_requests"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    transaction_hash: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    log_index: Mapped[int] = mapped_column(BigInteger, nullable=False)
    registration_momentum_height: Mapped[int] = mapped_column(
        BigInteger, nullable=False, index=True
    )
    network_class: Mapped[int] = mapped_column(Integer, nullable=False)
    chain_id: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    to_address: Mapped[str] = mapped_column(String(42), nullable=False, index=True)
    token_address: Mapped[str] = mapped_column(String(42), nullable=False)
    token_standard: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    token_symbol: Mapped[str] = mapped_column(String(20), nullable=False, index=True)
    token_decimals: Mapped[int] = mapped_column(Integer, nullable=False)
    amount: Mapped[int] = mapped_column(Numeric(78, 0), nullable=False)
    signature: Mapped[str] = mapped_column(String(100), nullable=False)
    redeemed: Mapped[bool] = mapped_column(Boolean, nullable=False, index=True)
    revoked: Mapped[bool] = mapped_column(Boolean, nullable=False, index=True)
    redeemable_in: Mapped[int] = mapped_column(Integer, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )

    __table_args__ = (
        UniqueConstraint(
            "transaction_hash", "log_index", name="uq_unwrap_tx_log"
        ),
        Index(
            "ix_unwrap_chain_token", "chain_id", "token_standard"
        ),
        Index(
            "ix_unwrap_momentum_desc", registration_momentum_height.desc()
        ),
    )

    def __repr__(self) -> str:
        return f"<UnwrapTokenRequest(id={self.id}, tx_hash={self.transaction_hash[:16]}..., amount={self.amount})>"
