"""PostgreSQL implementations of the Cosmos read/queries and device Tokens.

Method signatures intentionally mirror ``services.cosmos_service.CosmosService``
so the poller and HTTP endpoints require no logic changes.
"""

import json
import logging
from datetime import datetime, timezone
from typing import List, Optional

from sqlalchemy import delete, select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from .db import DeviceTokenRow, OrderLocationHistoryRow, OrderRow, TelemetryRow
from models.documents import DeviceTokenDocument, TelemetryDocument

logger = logging.getLogger(__name__)


class TelemetryStore:
    """Replaces CosmosService (telemetry + device token queries).

    Benefits over the Cosmos version: row-level upserts, real ORDER BY,
    and a single-DELETE expiry cleanup instead of the cross-partition
    scan-and-delete loop.
    """

    def __init__(self, session_factory) -> None:
        self._session_factory = session_factory

    async def _fetch_one(self, stmt) -> Optional[TelemetryRow]:
        async with self._session_factory() as session:
            row = (await session.execute(stmt)).scalar_one_or_none()
            return row

    async def get_previous_state(self, device_id: str) -> Optional[TelemetryDocument]:
        stmt = (
            select(TelemetryRow)
            .where(TelemetryRow.device_id == device_id)
            .order_by(TelemetryRow.status_updated_at.desc())
            .limit(1)
        )
        row = await self._fetch_one(stmt)
        if row is None:
            return None
        return TelemetryDocument.from_cosmos_dict(row.doc)

    async def get_history(self, device_id: str, limit: int = 50, hours: int = 24) -> List[TelemetryDocument]:
        since = (datetime.now(timezone.utc) - __import__("datetime").timedelta(hours=hours)).isoformat()
        stmt = (
            select(TelemetryRow)
            .where(TelemetryRow.device_id == device_id, TelemetryRow.status_updated_at >= since)
            .order_by(TelemetryRow.status_updated_at.desc())
            .limit(limit)
        )
        async with self._session_factory() as session:
            rows = (await session.execute(stmt)).scalars().all()
        return [TelemetryDocument.from_cosmos_dict(r.doc) for r in rows]

    async def get_events(self, device_id: str, limit: int = 20) -> List[TelemetryDocument]:
        stmt = (
            select(TelemetryRow)
            .where(TelemetryRow.device_id == device_id, TelemetryRow.event.is_not(None))
            .order_by(TelemetryRow.status_updated_at.desc())
            .limit(limit)
        )
        async with self._session_factory() as session:
            rows = (await session.execute(stmt)).scalars().all()
        return [TelemetryDocument.from_cosmos_dict(r.doc) for r in rows]

    async def save_state(self, doc: TelemetryDocument) -> None:
        """Insert a telemetry document (upsert semantics).

        Replaces the Functions cosmos_db_output binding write in poll_telemetry.
        """
        payload = doc.to_cosmos_dict()
        stmt = (
            pg_insert(TelemetryRow)
            .values(
                id=doc.id,
                device_id=doc.deviceId,
                status_updated_at=doc.status_updated_at,
                event=doc.eventTriggered,
                doc=payload,
            )
            .on_conflict_do_update(
                index_elements=["id"],
                set_={
                    "status_updated_at": doc.status_updated_at,
                    "event": doc.eventTriggered,
                    "doc": payload,
                },
            )
        )
        async with self._session_factory() as session:
            await session.execute(stmt)
            await session.commit()

    # ---------------- FCM device tokens ---------------- #

    async def register_device_token(self, user_id: str, fcm_token: str, platform: str = "android") -> bool:
        try:
            now = datetime.now(timezone.utc)
            iso = now.isoformat()
            stmt = (
                pg_insert(DeviceTokenRow)
                .values(
                    id=f"{user_id}:{fcm_token[:16]}",  # stable natural key
                    user_id=user_id,
                    fcm_token=fcm_token,
                    platform=platform,
                    registered_at=iso,
                    last_active_at=iso,
                    last_active_ts=now,
                    doc=DeviceTokenDocument.new_token(user_id, fcm_token, platform).to_cosmos_dict(),
                )
                .on_conflict_do_update(
                    index_elements=["id"],
                    set_={"last_active_at": iso, "last_active_ts": now, "platform": platform},
                )
            )
            async with self._session_factory() as session:
                await session.execute(stmt)
                await session.commit()
            return True
        except Exception:
            logger.exception("Error registering device token for user %s", user_id)
            return False

    async def unregister_device_token(self, user_id: str, fcm_token: str) -> bool:
        try:
            stmt = delete(DeviceTokenRow).where(
                DeviceTokenRow.user_id == user_id,
                DeviceTokenRow.fcm_token == fcm_token,
            )
            async with self._session_factory() as session:
                result = await session.execute(stmt)
                await session.commit()
            return result.rowcount > 0
        except Exception:
            logger.exception("Error unregistering device token for user %s", user_id)
            return False

    async def get_user_device_tokens(self, user_id: str, exclude_expired: bool = True, days_threshold: int = 30) -> List[str]:
        stmt = select(DeviceTokenRow).where(DeviceTokenRow.user_id == user_id)
        async with self._session_factory() as session:
            rows = (await session.execute(stmt)).scalars().all()
        doc_by_row = {r.id: DeviceTokenDocument.from_cosmos_dict(r.doc) for r in rows}
        tokens: List[str] = []
        for row in rows:
            token_doc = doc_by_row[row.id]
            if exclude_expired and token_doc.is_expired(days_threshold):
                continue
            tokens.append(row.fcm_token)
        return tokens

    async def cleanup_expired_tokens(self, days_threshold: int = 30) -> int:
        """One-statement cleanup — replaces the Cosmos cross-partition loop."""
        import datetime as _dt

        cutoff = _dt.datetime.now(_dt.timezone.utc) - _dt.timedelta(days=days_threshold)
        stmt = delete(DeviceTokenRow).where(DeviceTokenRow.last_active_ts < cutoff)
        async with self._session_factory() as session:
            result = await session.execute(stmt)
            await session.commit()
        return result.rowcount or 0


class PostgresOrderRepository:
    """Drop-in replacement for ``repositories.order_repository.OrderRepository``.

    Keeps the dict-based interface (`OrderService` expects dicts), converting
    to/from the JSONB `doc` column.
    """

    def __init__(self, session_factory) -> None:
        self._session_factory = session_factory

    async def create(self, order) -> dict:
        payload = order.model_dump()
        async with self._session_factory() as session:
            session.add(
                OrderRow(
                    id=payload["id"],
                    tracking_id=payload["tracking_id"],
                    status=payload["status"],
                    created_at=payload["created_at"],
                    created_ts=datetime.now(timezone.utc),
                    doc=payload,
                )
            )
            await session.commit()
        return payload

    async def _get_row(self, session: AsyncSession, order_id: str) -> Optional[OrderRow]:
        return (await session.execute(select(OrderRow).where(OrderRow.id == order_id))).scalar_one_or_none()

    async def get_by_tracking_id(self, tracking_id: str) -> Optional[dict]:
        async with self._session_factory() as session:
            row = (
                await session.execute(select(OrderRow).where(OrderRow.tracking_id == tracking_id))
            ).scalar_one_or_none()
            return row.doc if row else None

    async def get_active_orders(self) -> List[dict]:
        async with self._session_factory() as session:
            rows = (
                await session.execute(select(OrderRow).where(OrderRow.status == "active"))
            ).scalars().all()
        return [r.doc for r in rows]

    async def get_latest_active_order(self) -> Optional[dict]:
        async with self._session_factory() as session:
            row = (
                await session.execute(
                    select(OrderRow)
                    .where(OrderRow.status == "active")
                    .order_by(OrderRow.created_ts.desc())
                    .limit(1)
                )
            ).scalar_one_or_none()
            return row.doc if row else None

    async def get_by_id(self, order_id: str) -> Optional[dict]:
        async with self._session_factory() as session:
            row = await self._get_row(session, order_id)
            return row.doc if row else None

    async def update(self, order_dict: dict) -> dict:
        async with self._session_factory() as session:
            row = await self._get_row(session, order_dict["id"])
            if row is None:
                # Upsert for parity with Cosmos upsert_item
                row = OrderRow(
                    id=order_dict["id"],
                    tracking_id=order_dict.get("tracking_id", ""),
                    status=order_dict.get("status", "active"),
                    created_at=order_dict.get("created_at", ""),
                    created_ts=datetime.now(timezone.utc),
                    doc=order_dict,
                )
                session.add(row)
            else:
                row.status = order_dict.get("status", row.status)
                row.doc = order_dict
            await session.commit()
        return order_dict

    async def add_location_history(
        self, order_id: str, tracking_id: str, lat: float, lng: float, timestamp: str
    ) -> Optional[dict]:
        from models.order import OrderLocationHistory

        record = OrderLocationHistory(
            order_id=order_id, tracking_id=tracking_id, lat=lat, lng=lng, timestamp=timestamp
        )
        try:
            import uuid as _uuid

            async with self._session_factory() as session:
                session.add(
                    OrderLocationHistoryRow(
                        id=str(_uuid.uuid4()),
                        order_id=order_id,
                        tracking_id=tracking_id,
                        lat=lat,
                        lng=lng,
                        timestamp=timestamp,
                    )
                )
                await session.commit()
            return record.model_dump()
        except Exception:
            logger.exception("Error saving location history for order %s", order_id)
            return None

    async def get_location_history(self, tracking_id: str) -> List[dict]:
        async with self._session_factory() as session:
            rows = (
                await session.execute(
                    select(OrderLocationHistoryRow)
                    .where(OrderLocationHistoryRow.tracking_id == tracking_id)
                    .order_by(OrderLocationHistoryRow.recorded_ts.asc())
                )
            ).scalars().all()
        return [
            {
                "id": r.id,
                "order_id": r.order_id,
                "tracking_id": r.tracking_id,
                "lat": r.lat,
                "lng": r.lng,
                "timestamp": r.timestamp,
            }
            for r in rows
        ]
