"""Wrapper around the gps_obd2_tracker library for AIKA API integration."""

import logging
from datetime import datetime, timezone

from obdtracker import API, Location, DeviceStatus

from models.telemetry import LocationInfo, StatusInfo, TelemetryState

logger = logging.getLogger(__name__)


class AikaService:
    """Fetches current telemetry from the AIKA REST API.

    Uses the ``gps_obd2_tracker`` async library under the hood.
    A new HTTP session is created for each poll cycle and properly
    torn down to avoid leaking connections in a serverless context.
    """

    def __init__(self, server_url: str, device_id: str, password: str):
        self._server_url = server_url
        self._device_id = device_id
        self._password = password

    async def fetch_current_state(self, save_raw_payload: bool = False) -> TelemetryState:
        """Authenticate, poll, and return a ``TelemetryState`` snapshot.

        Args:
            save_raw_payload: If True, capture the full raw API response
                and attach it to the returned state.
        """

        async with API(self._server_url) as tracker:
            # Register updaters so the library fetches location + status
            tracker.register_updater(Location(tracker))
            tracker.register_updater(DeviceStatus(tracker))

            # Login with device credentials
            await tracker.login(self._device_id, self._password)

            if tracker.device_info is None:
                raise ValueError(
                    "AIKA Login failed: DeviceInfo is missing in server response. "
                    "Please check if your AIKA_SERVER_URL, AIKA_DEVICE_ID, and AIKA_PASSWORD "
                    "are correct and valid."
                )

            # Pull latest data
            await tracker.update()

            # --- Map library objects → our internal models ---

            location = LocationInfo(
                lat=float(tracker.location.lat) if tracker.location else 0.0,
                lng=float(tracker.location.lng) if tracker.location else 0.0,
                course=int(tracker.location.course) if tracker.location and hasattr(tracker.location, "course") else 0,
                position_time=tracker.location.position_time if tracker.location and hasattr(tracker.location, "position_time") else None,
            )

            status = StatusInfo(
                speed=float(tracker.location.speed) if tracker.location and hasattr(tracker.location, "speed") else 0.0,
                is_ignition_on=(
                    "acc on" in tracker.status.status.lower()
                ) if tracker.status and hasattr(tracker.status, "status") else False,
                battery_level=int(
                    tracker.status.battery
                ) if tracker.status and hasattr(tracker.status, "battery") else 0,
                is_online=(
                    "offline" not in tracker.status.status.lower()
                ) if tracker.status and hasattr(tracker.status, "status") else False,
            )

            # --- Capture raw payload if requested ---
            raw_payload = None
            if save_raw_payload:
                raw_payload = {
                    "location": {
                        k: getattr(tracker.location, k, None)
                        for k in vars(tracker.location)
                        if not k.startswith("_")
                    } if tracker.location else None,
                    "status": {
                        k: getattr(tracker.status, k, None)
                        for k in vars(tracker.status)
                        if not k.startswith("_")
                    } if tracker.status else None,
                    "device_info": {
                        k: getattr(tracker.device_info, k, None)
                        for k in vars(tracker.device_info)
                        if not k.startswith("_")
                    } if tracker.device_info else None,
                }

            state = TelemetryState(
                device_id=self._device_id,
                timestamp=datetime.now(timezone.utc).isoformat(),
                location=location,
                status=status,
                raw_payload=raw_payload,
            )

            logger.info(
                "Fetched state — speed=%.1f, ignition=%s, lat=%.4f, lng=%.4f",
                status.speed,
                status.is_ignition_on,
                location.lat,
                location.lng,
            )

            return state

    async def send_command(self, command_content: str) -> dict:
        """Send a command (e.g. DY or KY) to the tracking device."""
        async with API(self._server_url) as tracker:
            await tracker.login(self._device_id, self._password)
            if tracker.device_info is None:
                raise ValueError(
                    "AIKA Login failed: DeviceInfo is missing in server response. "
                    "Cannot send command since authentication failed."
                )
            res = await tracker.send_command(command_content)
            logger.info("Sent command %s — result=%s", command_content, res)
            return res

