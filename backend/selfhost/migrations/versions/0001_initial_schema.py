"""initial schema (baseline of selfhost/db.py models)

Revision ID: 0001
Revises:
Create Date: 2026-09-27

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB, TIMESTAMP

revision: str = "0001"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "telemetry",
        sa.Column("id", sa.String(), primary_key=True),
        sa.Column("device_id", sa.String(), nullable=False),
        sa.Column("status_updated_at", sa.String(), nullable=False),
        sa.Column(
            "updated_at_ts",
            TIMESTAMP(timezone=True),
            server_default=sa.text("now()"),
        ),
        sa.Column("event", sa.String(), nullable=True),
        sa.Column("doc", JSONB(), nullable=False),
    )
    op.create_index(
        "ix_telemetry_device_time", "telemetry", ["device_id", sa.text("status_updated_at DESC")]
    )
    op.create_index("ix_telemetry_device_event", "telemetry", ["device_id", "event"])

    op.create_table(
        "device_tokens",
        sa.Column("id", sa.String(), primary_key=True),
        sa.Column("user_id", sa.String(), nullable=False),
        sa.Column("fcm_token", sa.String(), nullable=False),
        sa.Column("platform", sa.String(), nullable=False, server_default="android"),
        sa.Column("registered_at", sa.String(), nullable=False),
        sa.Column("last_active_at", sa.String(), nullable=False),
        sa.Column("last_active_ts", TIMESTAMP(timezone=True), nullable=True),
        sa.Column("doc", JSONB(), nullable=False),
    )
    op.create_index("ix_device_tokens_user", "device_tokens", ["user_id", "fcm_token"])
    op.create_index("ix_device_tokens_last_active", "device_tokens", ["last_active_ts"])

    op.create_table(
        "orders",
        sa.Column("id", sa.String(), primary_key=True),
        sa.Column("tracking_id", sa.String(), nullable=False, unique=True),
        sa.Column("status", sa.String(), nullable=False, server_default="active"),
        sa.Column("created_at", sa.String(), nullable=False),
        sa.Column(
            "created_ts", TIMESTAMP(timezone=True), server_default=sa.text("now()")
        ),
        sa.Column("doc", JSONB(), nullable=False),
    )
    op.create_index(
        "ix_orders_status_created", "orders", ["status", sa.text("created_ts DESC")]
    )
    op.create_index("ix_orders_tracking_id", "orders", ["tracking_id"], unique=True)

    op.create_table(
        "order_location_history",
        sa.Column("id", sa.String(), primary_key=True),
        sa.Column("order_id", sa.String(), nullable=False),
        sa.Column("tracking_id", sa.String(), nullable=False),
        sa.Column("lat", sa.Float(), nullable=False),
        sa.Column("lng", sa.Float(), nullable=False),
        sa.Column("timestamp", sa.String(), nullable=False),
        sa.Column(
            "recorded_ts", TIMESTAMP(timezone=True), server_default=sa.text("now()")
        ),
    )
    op.create_index(
        "ix_olh_tracking_time", "order_location_history", ["tracking_id", "recorded_ts"]
    )


def downgrade() -> None:
    op.drop_index("ix_olh_tracking_time", table_name="order_location_history")
    op.drop_table("order_location_history")
    op.drop_index("ix_orders_tracking_id", table_name="orders")
    op.drop_index("ix_orders_status_created", table_name="orders")
    op.drop_table("orders")
    op.drop_index("ix_device_tokens_last_active", table_name="device_tokens")
    op.drop_index("ix_device_tokens_user", table_name="device_tokens")
    op.drop_table("device_tokens")
    op.drop_index("ix_telemetry_device_event", table_name="telemetry")
    op.drop_index("ix_telemetry_device_time", table_name="telemetry")
    op.drop_table("telemetry")
