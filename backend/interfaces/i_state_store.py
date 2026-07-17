"""Protocol for reading/querying persisted telemetry state."""

from typing import List, Optional, Protocol, runtime_checkable

from models.documents import TelemetryDocument


@runtime_checkable
class IStateStore(Protocol):
    """Abstraction over the state persistence layer (Cosmos DB)."""

    async def get_previous_state(
        self, device_id: str
    ) -> Optional[TelemetryDocument]:
        """Return the most recent telemetry document for *device_id*."""
        ...

    async def get_history(
        self, device_id: str, limit: int = 50, hours: int = 24
    ) -> List[TelemetryDocument]:
        """Return recent telemetry history."""
        ...

    async def get_events(
        self, device_id: str, limit: int = 20
    ) -> List[TelemetryDocument]:
        """Return recent documents where an event was triggered."""
        ...
