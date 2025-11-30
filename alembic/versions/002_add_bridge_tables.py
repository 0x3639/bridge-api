"""Add bridge wrap/unwrap token request tables

Revision ID: 002
Revises: 001
Create Date: 2024-01-15

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "002"
down_revision: Union[str, None] = "001"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Wrap Token Requests table (Zenon -> Ethereum)
    op.create_table(
        "wrap_token_requests",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("request_id", sa.String(64), nullable=False),
        sa.Column("network_class", sa.Integer(), nullable=False),
        sa.Column("chain_id", sa.Integer(), nullable=False),
        sa.Column("to_address", sa.String(42), nullable=False),
        sa.Column("token_standard", sa.String(50), nullable=False),
        sa.Column("token_address", sa.String(42), nullable=False),
        sa.Column("token_symbol", sa.String(20), nullable=False),
        sa.Column("token_decimals", sa.Integer(), nullable=False),
        sa.Column("amount", sa.Numeric(78, 0), nullable=False),
        sa.Column("fee", sa.Numeric(78, 0), nullable=False),
        sa.Column("signature", sa.String(100), nullable=False),
        sa.Column("creation_momentum_height", sa.BigInteger(), nullable=False),
        sa.Column("confirmations_to_finality", sa.Integer(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("request_id"),
    )

    # Wrap table indexes
    op.create_index("ix_wrap_request_id", "wrap_token_requests", ["request_id"])
    op.create_index("ix_wrap_chain_id", "wrap_token_requests", ["chain_id"])
    op.create_index("ix_wrap_to_address", "wrap_token_requests", ["to_address"])
    op.create_index("ix_wrap_token_standard", "wrap_token_requests", ["token_standard"])
    op.create_index("ix_wrap_token_symbol", "wrap_token_requests", ["token_symbol"])
    op.create_index(
        "ix_wrap_chain_token",
        "wrap_token_requests",
        ["chain_id", "token_standard"],
    )
    op.create_index(
        "ix_wrap_momentum_desc",
        "wrap_token_requests",
        [sa.text("creation_momentum_height DESC")],
    )

    # Unwrap Token Requests table (Ethereum -> Zenon)
    op.create_table(
        "unwrap_token_requests",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("transaction_hash", sa.String(64), nullable=False),
        sa.Column("log_index", sa.BigInteger(), nullable=False),
        sa.Column("registration_momentum_height", sa.BigInteger(), nullable=False),
        sa.Column("network_class", sa.Integer(), nullable=False),
        sa.Column("chain_id", sa.Integer(), nullable=False),
        sa.Column("to_address", sa.String(42), nullable=False),
        sa.Column("token_address", sa.String(42), nullable=False),
        sa.Column("token_standard", sa.String(50), nullable=False),
        sa.Column("token_symbol", sa.String(20), nullable=False),
        sa.Column("token_decimals", sa.Integer(), nullable=False),
        sa.Column("amount", sa.Numeric(78, 0), nullable=False),
        sa.Column("signature", sa.String(100), nullable=False),
        sa.Column("redeemed", sa.Boolean(), nullable=False),
        sa.Column("revoked", sa.Boolean(), nullable=False),
        sa.Column("redeemable_in", sa.Integer(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("transaction_hash", "log_index", name="uq_unwrap_tx_log"),
    )

    # Unwrap table indexes
    op.create_index("ix_unwrap_tx_hash", "unwrap_token_requests", ["transaction_hash"])
    op.create_index("ix_unwrap_chain_id", "unwrap_token_requests", ["chain_id"])
    op.create_index("ix_unwrap_to_address", "unwrap_token_requests", ["to_address"])
    op.create_index("ix_unwrap_token_standard", "unwrap_token_requests", ["token_standard"])
    op.create_index("ix_unwrap_token_symbol", "unwrap_token_requests", ["token_symbol"])
    op.create_index("ix_unwrap_redeemed", "unwrap_token_requests", ["redeemed"])
    op.create_index("ix_unwrap_revoked", "unwrap_token_requests", ["revoked"])
    op.create_index(
        "ix_unwrap_chain_token",
        "unwrap_token_requests",
        ["chain_id", "token_standard"],
    )
    op.create_index(
        "ix_unwrap_momentum_desc",
        "unwrap_token_requests",
        [sa.text("registration_momentum_height DESC")],
    )


def downgrade() -> None:
    op.drop_table("unwrap_token_requests")
    op.drop_table("wrap_token_requests")
