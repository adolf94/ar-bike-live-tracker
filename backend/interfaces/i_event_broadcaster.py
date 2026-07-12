"""Protocol for broadcasting events to connected clients."""

from typing import Any, Dict, Protocol


class IEventBroadcaster(Protocol):
    """Abstraction over the real-time event delivery mechanism (Web PubSub)."""

    async def broadcast_event(self, payload: Dict[str, Any]) -> None:
        """Push an event payload to all connected WebSocket clients."""
        ...

    def get_client_access_url(self) -> str:
        """Return a client-access URL (with token) for WebSocket negotiation."""
        ...
