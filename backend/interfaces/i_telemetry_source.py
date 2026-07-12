"""Protocol for fetching current telemetry from the GPS tracker API."""

from typing import Protocol

from models.telemetry import TelemetryState


class ITelemetrySource(Protocol):
    """Abstraction over the AIKA (or any future) telemetry data source."""

    async def fetch_current_state(self) -> TelemetryState:
        """Return the latest telemetry snapshot from the tracker."""
        ...
