"""Unit tests for services.event_engine.compute_event.

These tests are pure logic — no mocks, no I/O.
"""

import sys
import os
import pytest

# Ensure project root is on sys.path so imports resolve
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from models.telemetry import EventType, LocationInfo, StatusInfo, TelemetryState
from models.documents import TelemetryDocument
from services.event_engine import compute_event


# ====================================================================== #
#  Helpers
# ====================================================================== #


def _make_state(
    speed: float = 0.0,
    ignition: bool = False,
    lat: float = 14.5794,
    lng: float = 121.0594,
) -> TelemetryState:
    """Build a ``TelemetryState`` with sensible defaults."""
    return TelemetryState(
        device_id="test-device",
        timestamp="2026-07-11T12:00:00Z",
        location=LocationInfo(lat=lat, lng=lng, course=0),
        status=StatusInfo(
            speed=speed,
            is_ignition_on=ignition,
            battery_level=95,
            is_online=True,
        ),
    )


def _make_previous(
    speed: float = 0.0, ignition: bool = False
) -> TelemetryDocument:
    """Build a ``TelemetryDocument`` representing the previous state."""
    return TelemetryDocument(
        id="prev-001",
        deviceId="test-device",
        status_updated_at="2026-07-11T11:59:50Z",
        location={"lat": 14.5794, "lng": 121.0594, "course": 0},
        status={
            "speed": speed,
            "isIgnitionOn": ignition,
            "batteryLevel": 95,
            "isOnline": True,
        },
        eventTriggered=None,
    )


# ====================================================================== #
#  Test: No previous state (first poll ever)
# ====================================================================== #


class TestFirstPoll:
    def test_no_event_on_first_poll(self):
        current = _make_state(speed=15.0, ignition=True)
        result = compute_event(current, None, enable_security_alert=False)
        assert result is None


# ====================================================================== #
#  Test: Movement Started (Section 4.1)
# ====================================================================== #


class TestMovementStarted:
    def test_movement_started_by_speed(self):
        """speed transitions from 0 → 15 km/h."""
        current = _make_state(speed=15.0, ignition=True)
        previous = _make_previous(speed=0.0, ignition=True)
        result = compute_event(current, previous)
        assert result == EventType.MOVEMENT_STARTED

    def test_movement_started_by_ignition(self):
        """Ignition transitions from OFF → ON (speed still low)."""
        current = _make_state(speed=2.0, ignition=True)
        previous = _make_previous(speed=0.0, ignition=False)
        result = compute_event(current, previous)
        assert result == EventType.MOVEMENT_STARTED

    def test_movement_started_speed_crosses_threshold(self):
        """Speed crosses the 5 km/h threshold from below."""
        current = _make_state(speed=6.0, ignition=True)
        previous = _make_previous(speed=4.0, ignition=True)
        result = compute_event(current, previous)
        assert result == EventType.MOVEMENT_STARTED


# ====================================================================== #
#  Test: Movement Stopped (Section 4.2)
# ====================================================================== #


class TestMovementStopped:
    def test_movement_stopped(self):
        """Speed drops from 30 → 0 (ignition remains ON)."""
        current = _make_state(speed=0.0, ignition=True)
        previous = _make_previous(speed=30.0, ignition=True)
        result = compute_event(current, previous)
        assert result == EventType.MOVEMENT_STOPPED

    def test_movement_stopped_from_low_speed(self):
        """Speed drops from 3 → 0 (ignition remains ON)."""
        current = _make_state(speed=0.0, ignition=True)
        previous = _make_previous(speed=3.0, ignition=True)
        result = compute_event(current, previous)
        assert result == EventType.MOVEMENT_STOPPED

    def test_engine_off_by_ignition(self):
        """Ignition transitions from ON → OFF (speed remains 0)."""
        current = _make_state(speed=0.0, ignition=False)
        previous = _make_previous(speed=0.0, ignition=True)
        result = compute_event(current, previous)
        assert result == EventType.ENGINE_OFF

    def test_engine_off_while_moving(self):
        """Ignition transitions from ON → OFF while moving (speed drops 30 -> 0)."""
        current = _make_state(speed=0.0, ignition=False)
        previous = _make_previous(speed=30.0, ignition=True)
        result = compute_event(current, previous)
        assert result == EventType.ENGINE_OFF


# ====================================================================== #
#  Test: No Event (routine poll)
# ====================================================================== #


class TestRoutinePoll:
    def test_no_event_constant_speed(self):
        """Speed stays constant above threshold — no state change."""
        current = _make_state(speed=35.0, ignition=True)
        previous = _make_previous(speed=30.0, ignition=True)
        result = compute_event(current, previous)
        assert result is None

    def test_no_event_both_stationary(self):
        """Both current and previous at speed 0."""
        current = _make_state(speed=0.0, ignition=False)
        previous = _make_previous(speed=0.0, ignition=False)
        result = compute_event(current, previous)
        assert result is None


# ====================================================================== #
#  Test: Unauthorized Movement (Section 4.3)
# ====================================================================== #


class TestUnauthorizedMovement:
    def test_unauthorized_movement_when_enabled(self):
        """Speed > 5 km/h with ignition OFF and flag enabled."""
        current = _make_state(speed=10.0, ignition=False)
        previous = _make_previous(speed=0.0, ignition=False)
        result = compute_event(current, previous, enable_security_alert=True)
        assert result == EventType.UNAUTHORIZED_MOVEMENT

    def test_unauthorized_movement_when_disabled(self):
        """Same conditions but flag disabled — should fall through to
        movement_started (speed transition) instead."""
        current = _make_state(speed=10.0, ignition=False)
        previous = _make_previous(speed=0.0, ignition=False)
        result = compute_event(current, previous, enable_security_alert=False)
        # Ignition didn't change (both False), but speed crossed threshold
        assert result == EventType.MOVEMENT_STARTED

    def test_unauthorized_takes_priority_over_movement_started(self):
        """When security is enabled, unauthorized_movement takes priority
        over movement_started even if the speed threshold is also crossed."""
        current = _make_state(speed=10.0, ignition=False)
        previous = _make_previous(speed=3.0, ignition=False)
        result = compute_event(current, previous, enable_security_alert=True)
        assert result == EventType.UNAUTHORIZED_MOVEMENT


# ====================================================================== #
#  Test: Document model helpers
# ====================================================================== #


class TestTelemetryDocument:
    def test_from_state_without_event(self):
        state = _make_state(speed=10.0, ignition=True)
        doc = TelemetryDocument.from_state(state)
        assert doc.deviceId == "test-device"
        assert doc.eventTriggered is None
        assert doc.ttl == 5_184_000

    def test_from_state_with_event(self):
        state = _make_state(speed=10.0, ignition=True)
        doc = TelemetryDocument.from_state(state, EventType.MOVEMENT_STARTED)
        assert doc.eventTriggered == "movement_started"

    def test_roundtrip_cosmos_dict(self):
        state = _make_state(speed=25.0, ignition=True)
        doc = TelemetryDocument.from_state(state, EventType.MOVEMENT_STOPPED)
        cosmos_dict = doc.to_cosmos_dict()
        restored = TelemetryDocument.from_cosmos_dict(cosmos_dict)
        assert restored.id == doc.id
        assert restored.deviceId == doc.deviceId
        assert restored.eventTriggered == "movement_stopped"
        assert restored.speed == 25.0
        assert restored.is_ignition_on is True
