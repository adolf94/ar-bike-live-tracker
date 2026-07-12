"""Internal telemetry data models used across the application."""

from dataclasses import dataclass, asdict
from enum import Enum
from typing import Any, Dict, Optional


class EventType(str, Enum):
    """Types of events that can be triggered by state-comparison logic."""

    MOVEMENT_STARTED = "movement_started"
    MOVEMENT_STOPPED = "movement_stopped"
    UNAUTHORIZED_MOVEMENT = "unauthorized_movement"
    ENGINE_OFF = "engine_off"


@dataclass(frozen=True)
class LocationInfo:
    """GPS location snapshot."""

    lat: float
    lng: float
    course: int = 0
    position_time: Optional[str] = None

    def to_dict(self) -> dict:
        d = {
            "lat": self.lat,
            "lng": self.lng,
            "course": self.course,
        }
        if self.position_time is not None:
            d["position_time"] = self.position_time
        return d


@dataclass(frozen=True)
class StatusInfo:
    """Vehicle / device status snapshot."""

    speed: float
    is_ignition_on: bool
    battery_level: int
    is_online: bool

    def to_dict(self) -> dict:
        return {
            "speed": self.speed,
            "isIgnitionOn": self.is_ignition_on,
            "batteryLevel": self.battery_level,
            "isOnline": self.is_online,
        }


@dataclass
class TelemetryState:
    """In-memory representation of a single poll result from the AIKA API.

    This is the *current* snapshot before it is persisted as a
    ``TelemetryDocument``.
    """

    device_id: str
    timestamp: str  # ISO 8601
    location: LocationInfo
    status: StatusInfo
    event_triggered: Optional[EventType] = None
    raw_payload: Optional[Dict[str, Any]] = None
