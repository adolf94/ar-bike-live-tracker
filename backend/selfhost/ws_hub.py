"""Native WebSocket hub — replaces Azure Web PubSub + SignalR publishers.

Groups map directly to the old model:
    - ``telemetry``            (bike position, all listeners)
    - ``order-{trackingId}``   (HatidKuya per-order tracking)

The frontend swaps ``useWebPubSub``/``useHatidKuyaSignalR`` negotiate+npm
client calls for a plain ``new WebSocket("wss://<host>/ws/<group>")``.
"""

import asyncio
import json
import logging
from typing import Dict, List, Set

from fastapi import WebSocket, WebSocketDisconnect

logger = logging.getLogger(__name__)


class ConnectionGroup:
    def __init__(self) -> None:
        self.connections: Set[WebSocket] = set()
        self.lock = asyncio.Lock()

    async def add(self, ws: WebSocket) -> None:
        async with self.lock:
            self.connections.add(ws)

    async def remove(self, ws: WebSocket) -> None:
        async with self.lock:
            self.connections.discard(ws)

    def count(self) -> int:
        return len(self.connections)


class EventHub:
    """In-process pub/sub for WebSocket clients.

    Single-process only (fine for one home server). If you ever run
    multiple replicas, swap this for Redis pub/sub — the interface
    (join/publish) is designed to allow that.
    """

    def __init__(self) -> None:
        self._groups: Dict[str, ConnectionGroup] = {}
        self._lock = asyncio.Lock()

    def _group(self, name: str) -> ConnectionGroup:
        if name not in self._groups:
            self._groups[name] = ConnectionGroup()
        return self._groups[name]

    async def connect(self, ws: WebSocket, group: str) -> None:
        await ws.accept()
        await self._group(group).add(ws)
        logger.info("WS connected group=%s total=%d", group, self._group(group).count())

    async def disconnect(self, ws: WebSocket, group: str) -> None:
        await self._group(group).remove(ws)
        logger.info("WS disconnected group=%s total=%d", group, self._group(group).count())

    async def publish(self, group: str, payload: dict) -> int:
        """Send JSON to every connection in *group*; prunes dead sockets."""
        dead: List[WebSocket] = []
        sent = 0
        grp = self._group(group)
        for ws in list(grp.connections):
            try:
                await ws.send_text(json.dumps(payload))
                sent += 1
            except Exception:
                dead.append(ws)
        for ws in dead:
            await grp.remove(ws)
        return sent

    def group_size(self, group: str) -> int:
        return self._groups.get(group, ConnectionGroup()).count()


hub = EventHub()

TELEMETRY_GROUP = "telemetry"


def order_group(tracking_id: str) -> str:
    return f"order-{tracking_id}"
