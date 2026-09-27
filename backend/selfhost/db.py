"""SQLAlchemy async engine, sessions, and table definitions.

Catalog mapping:
    Cosmos `Telemetry` container          -> telemetry table
    Cosmos `DeviceTokens` container       -> device_tokens table
    Cosmos `Orders` container             -> orders table
    Cosmos `OrderLocationHistory`         -> order_location_history table

Documents are stored as JSONB so the existing Pydantic models / dicts
serialize without any schema translation; indexed columns are extracted
for the queries the app actually runs.
"""

import asyncio
import os

from sqlalchemy import (
    Column,
    Float,
    Index,
    Integer,
    String,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB, TIMESTAMP
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool
from sqlalchemy.orm import declarative_base

DATABASE_URL = os.environ.get(
    "DATABASE_URL",
    "postgresql+asyncpg://tracker:tracker@localhost:5432/biketracker",
)

# NullPool: repository calls in this app can run on several event loops
# (the main uvicorn loop, plus fresh loops from sync_bridge worker threads).
# asyncpg connections are bound to the loop that created them, so pooled
# connections must never be reused across loops.
engine = create_async_engine(DATABASE_URL, poolclass=NullPool, pool_pre_ping=True)
SessionLocal = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

Base = declarative_base()


class TelemetryRow(Base):
    __tablename__ = "telemetry"

    id = Column(String, primary_key=True)                # uuid7 doc id
    device_id = Column(String, nullable=False)           # /deviceId partition
    status_updated_at = Column(String, nullable=False)
    updated_at_ts = Column(TIMESTAMP(timezone=True), server_default=text("now()"))
    event = Column(String, nullable=True)                # eventTriggered
    doc = Column(JSONB, nullable=False)                  # full TelemetryDocument dict


# SELECT TOP 1 ... WHERE deviceId=@d ORDER BY status_updated_at DESC
Index("ix_telemetry_device_time", TelemetryRow.device_id, TelemetryRow.status_updated_at.desc())
# ... AND IS_DEFINED(c.eventTriggered) AND c.eventTriggered != null
Index("ix_telemetry_device_event", TelemetryRow.device_id, TelemetryRow.event)


class DeviceTokenRow(Base):
    __tablename__ = "device_tokens"

    id = Column(String, primary_key=True)
    user_id = Column(String, nullable=False)             # /userId partition
    fcm_token = Column(String, nullable=False)
    platform = Column(String, nullable=False, default="android")
    registered_at = Column(String, nullable=False)
    last_active_at = Column(String, nullable=False)
    last_active_ts = Column(TIMESTAMP(timezone=True))    # for expiry cleanup
    doc = Column(JSONB, nullable=False)


Index("ix_device_tokens_user", DeviceTokenRow.user_id, DeviceTokenRow.fcm_token)
Index("ix_device_tokens_last_active", DeviceTokenRow.last_active_ts)


class OrderRow(Base):
    __tablename__ = "orders"

    id = Column(String, primary_key=True)
    tracking_id = Column(String, nullable=False, unique=True)  # /tracking_id partition
    status = Column(String, nullable=False, default="active")
    created_at = Column(String, nullable=False)
    created_ts = Column(TIMESTAMP(timezone=True), server_default=text("now()"))
    doc = Column(JSONB, nullable=False)                  # full Order model_dump()


# SELECT TOP 1 ... WHERE status='active' ORDER BY created_at DESC
Index("ix_orders_status_created", OrderRow.status, OrderRow.created_ts.desc())
Index("ix_orders_tracking_id", OrderRow.tracking_id, unique=True)


class OrderLocationHistoryRow(Base):
    __tablename__ = "order_location_history"

    id = Column(String, primary_key=True)
    order_id = Column(String, nullable=False)
    tracking_id = Column(String, nullable=False)         # /tracking_id partition
    lat = Column(Float, nullable=False)
    lng = Column(Float, nullable=False)
    timestamp = Column(String, nullable=False)
    recorded_ts = Column(TIMESTAMP(timezone=True), server_default=text("now()"))


Index("ix_olh_tracking_time", OrderLocationHistoryRow.tracking_id, OrderLocationHistoryRow.recorded_ts)


def _run_migrations_sync() -> None:
    """Run `alembic upgrade head` on a worker thread (sync psycopg2)."""
    from alembic import command
    from alembic.config import Config

    # alembic.ini lives at the backend root (script_location is
    # relative to %(there)s), not next to db.py.
    alembic_cfg = Config(
        os.path.join(
            os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
            "alembic.ini",
        )
    )
    command.upgrade(alembic_cfg, "head")


async def init_db() -> None:
    """Bring the schema to the latest version via Alembic on startup.

    `upgrade head` is idempotent: brand-new databases get the full
    baseline, existing ones get only pending migrations.
    """
    await asyncio.to_thread(_run_migrations_sync)
