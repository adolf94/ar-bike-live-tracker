"""Cosmos DB document schema — matches spec Section 3."""

from __future__ import annotations

import uuid
import uuid_utils
from dataclasses import dataclass, field
from datetime import timedelta
from typing import Any, Dict, Optional

from .telemetry import EventType, LocationInfo, StatusInfo, TelemetryState

# 60 days in seconds
DEFAULT_TTL_SECONDS = 5_184_000


@dataclass
class TelemetryDocument:
    """Represents a single telemetry record persisted to Cosmos DB.

    Schema::

        {
          "id": "uuid-v7",
          "deviceId": "string",
          "timestamp": "ISO-8601",
          "location": { "lat": float, "lng": float, "course": int },
          "status":   { "speed": float, "isIgnitionOn": bool,
                        "batteryLevel": int, "isOnline": bool },
          "eventTriggered": "movement_started" | null,
          "rawPayload": { ... } | null,
          "ttl": 5184000
        }
    """

    id: str
    deviceId: str
    status_updated_at: str
    location: Dict[str, Any]
    status: Dict[str, Any]
    eventTriggered: Optional[str] = None
    rawPayload: Optional[Dict[str, Any]] = None
    ttl: int = field(default=DEFAULT_TTL_SECONDS)
    last_checked_at: Optional[str] = None

    # ------------------------------------------------------------------ #
    #  Factory helpers
    # ------------------------------------------------------------------ #

    @classmethod
    def from_state(
        cls,
        state: TelemetryState,
        event: Optional[EventType] = None,
    ) -> "TelemetryDocument":
        """Build a document from an in-memory ``TelemetryState``."""
        return cls(
            id=str(uuid_utils.uuid7()),
            deviceId=state.device_id,
            status_updated_at=state.timestamp,
            location=state.location.to_dict(),
            status=state.status.to_dict(),
            eventTriggered=event.value if event else None,
            rawPayload=state.raw_payload,
            last_checked_at=state.timestamp,
        )

    @classmethod
    def from_cosmos_dict(cls, data: Dict[str, Any]) -> "TelemetryDocument":
        """Deserialise a Cosmos DB query result into a document."""
        return cls(
            id=data["id"],
            deviceId=data["deviceId"],
            status_updated_at=data["status_updated_at"],
            location=data["location"],
            status=data["status"],
            eventTriggered=data.get("eventTriggered"),
            rawPayload=data.get("rawPayload"),
            ttl=data.get("ttl", DEFAULT_TTL_SECONDS),
            last_checked_at=data.get("last_checked_at"),
        )

    # ------------------------------------------------------------------ #
    #  Serialisation
    # ------------------------------------------------------------------ #

    def to_cosmos_dict(self) -> Dict[str, Any]:
        """Serialise for the Cosmos DB output binding."""
        doc = {
            "id": self.id,
            "deviceId": self.deviceId,
            "status_updated_at": self.status_updated_at,
            "location": self.location,
            "status": self.status,
            "eventTriggered": self.eventTriggered,
            "ttl": self.ttl,
        }
        if self.last_checked_at is not None:
            doc["last_checked_at"] = self.last_checked_at
        if self.rawPayload is not None:
            doc["rawPayload"] = self.rawPayload
        return doc

    # ------------------------------------------------------------------ #
    #  Convenience accessors (used by event engine)
    # ------------------------------------------------------------------ #

    @property
    def speed(self) -> float:
        return float(self.status.get("speed", 0))

    @property
    def is_ignition_on(self) -> bool:
        return bool(self.status.get("isIgnitionOn", False))

    @property
    def is_online(self) -> bool:
        return bool(self.status.get("isOnline", True))


@dataclass
class DeviceTokenDocument:
    """Represents an FCM device token registered for push notifications.
    
    Schema::
    
        {
          "id": "fcm_token_hash_or_uuid",
          "userId": "subject_claim_from_jwt",
          "fcmToken": "string",
          "platform": "android",
          "registeredAt": "ISO-8601",
          "lastActiveAt": "ISO-8601"
        }
    """
    
    id: str
    userId: str
    fcmToken: str
    platform: str
    registeredAt: str
    lastActiveAt: str
    ttl: int = field(default=DEFAULT_TTL_SECONDS)
    
    # ------------------------------------------------------------------ #
    #  Factory helpers
    # ------------------------------------------------------------------ #
    
    @classmethod
    def new_token(
        cls,
        user_id: str,
        fcm_token: str,
        platform: str = "android",
    ) -> "DeviceTokenDocument":
        """Create a new device token document."""
        import uuid_utils
        from datetime import datetime
        
        current_time = datetime.now().isoformat()
        return cls(
            id=str(uuid_utils.uuid7()),
            userId=user_id,
            fcmToken=fcm_token,
            platform=platform,
            registeredAt=current_time,
            lastActiveAt=current_time,
        )
    
    @classmethod
    def from_cosmos_dict(cls, data: Dict[str, Any]) -> "DeviceTokenDocument":
        """Deserialise a Cosmos DB query result into a device token document."""
        return cls(
            id=data["id"],
            userId=data["userId"],
            fcmToken=data["fcmToken"],
            platform=data["platform"],
            registeredAt=data["registeredAt"],
            lastActiveAt=data["lastActiveAt"],
            ttl=data.get("ttl", DEFAULT_TTL_SECONDS),
        )
    
    # ------------------------------------------------------------------ #
    #  Serialisation
    # ------------------------------------------------------------------ #
    
    def to_cosmos_dict(self) -> Dict[str, Any]:
        """Serialise for the Cosmos DB output binding."""
        return {
            "id": self.id,
            "userId": self.userId,
            "fcmToken": self.fcmToken,
            "platform": self.platform,
            "registeredAt": self.registeredAt,
            "lastActiveAt": self.lastActiveAt,
            "ttl": self.ttl,
        }
    
    # ------------------------------------------------------------------ #
    #  Methods
    # ------------------------------------------------------------------ #
    
    def update_last_active(self) -> None:
        """Update the lastActiveAt timestamp to current time."""
        from datetime import datetime
        self.lastActiveAt = datetime.now().isoformat()
    
    def is_expired(self, days_threshold: int = 30) -> bool:
        """Check if the token is considered expired (not active for threshold days)."""
        from datetime import datetime
        
        last_active = datetime.fromisoformat(self.lastActiveAt)
        cutoff = datetime.now().utcnow() - timedelta(days=days_threshold)
        return last_active < cutoff
