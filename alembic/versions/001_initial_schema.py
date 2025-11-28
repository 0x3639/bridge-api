"""Initial database schema

Revision ID: 001
Revises:
Create Date: 2024-01-01

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "001"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Users table
    op.create_table(
        "users",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("username", sa.String(50), nullable=False),
        sa.Column("email", sa.String(255), nullable=False),
        sa.Column("password_hash", sa.String(255), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False, default=True),
        sa.Column("is_admin", sa.Boolean(), nullable=False, default=False),
        sa.Column("rate_limit_per_second", sa.Integer(), nullable=False, default=10),
        sa.Column("rate_limit_burst", sa.Integer(), nullable=False, default=20),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("username"),
        sa.UniqueConstraint("email"),
    )
    op.create_index("idx_users_username", "users", ["username"])
    op.create_index("idx_users_email", "users", ["email"])

    # API Tokens table
    op.create_table(
        "api_tokens",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("token_hash", sa.String(64), nullable=False),
        sa.Column("name", sa.String(100), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("is_revoked", sa.Boolean(), nullable=False, default=False),
        sa.Column("last_used_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.UniqueConstraint("token_hash"),
    )
    op.create_index("idx_api_tokens_user_id", "api_tokens", ["user_id"])
    op.create_index("idx_api_tokens_token_hash", "api_tokens", ["token_hash"])

    # Orchestrator Nodes table
    op.create_table(
        "orchestrator_nodes",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("name", sa.String(100), nullable=False),
        sa.Column("ip_address", postgresql.INET(), nullable=False),
        sa.Column("pubkey", sa.String(100), nullable=True),
        sa.Column("rpc_port", sa.Integer(), nullable=False, default=55000),
        sa.Column("is_active", sa.Boolean(), nullable=False, default=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("name"),
    )

    # Orchestrator Snapshots table
    op.create_table(
        "orchestrator_snapshots",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("node_id", sa.Integer(), nullable=False),
        sa.Column(
            "timestamp",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column("pillar_name", sa.String(100), nullable=True),
        sa.Column("producer_address", sa.String(100), nullable=True),
        sa.Column("state", sa.Integer(), nullable=True),
        sa.Column("state_name", sa.String(50), nullable=True),
        sa.Column("is_online", sa.Boolean(), nullable=False, default=False),
        sa.Column("response_time_ms", sa.Integer(), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("raw_identity", postgresql.JSONB(), nullable=True),
        sa.Column("raw_status", postgresql.JSONB(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["node_id"], ["orchestrator_nodes.id"]),
    )
    op.create_index(
        "idx_snapshots_node_timestamp",
        "orchestrator_snapshots",
        ["node_id", sa.text("timestamp DESC")],
    )
    op.create_index(
        "idx_snapshots_timestamp",
        "orchestrator_snapshots",
        [sa.text("timestamp DESC")],
    )

    # Network Stats table
    op.create_table(
        "network_stats",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("snapshot_id", sa.BigInteger(), nullable=False),
        sa.Column("network", sa.String(20), nullable=False),
        sa.Column("wraps_count", sa.Integer(), nullable=False, default=0),
        sa.Column("unwraps_count", sa.Integer(), nullable=False, default=0),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(
            ["snapshot_id"], ["orchestrator_snapshots.id"], ondelete="CASCADE"
        ),
    )
    op.create_index("idx_network_stats_snapshot", "network_stats", ["snapshot_id"])


def downgrade() -> None:
    op.drop_table("network_stats")
    op.drop_table("orchestrator_snapshots")
    op.drop_table("orchestrator_nodes")
    op.drop_table("api_tokens")
    op.drop_table("users")
