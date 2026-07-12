"""Unit tests for the new position_time field and conditional persistence logic."""

import sys
import os
import pytest

# Ensure project root is on sys.path so imports resolve
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from models.telemetry import LocationInfo, StatusInfo, TelemetryState
from models.documents import TelemetryDocument


def test_location_info_serialization_with_position_time():
    # 1. Without position_time
    loc_without = LocationInfo(lat=14.55043, lng=121.07967, course=233)
    serialized_without = loc_without.to_dict()
    assert "position_time" not in serialized_without
    assert serialized_without["lat"] == 14.55043
    assert serialized_without["lng"] == 121.07967
    assert serialized_without["course"] == 233

    # 2. With position_time
    loc_with = LocationInfo(lat=14.55043, lng=121.07967, course=233, position_time="2026-07-12 10:14:00")
    serialized_with = loc_with.to_dict()
    assert serialized_with["position_time"] == "2026-07-12 10:14:00"
    assert serialized_with["lat"] == 14.55043
    assert serialized_with["lng"] == 121.07967
    assert serialized_with["course"] == 233


def test_conditional_save_checking():
    previous_doc = TelemetryDocument(
        id="prev-id-123",
        deviceId="test-device",
        status_updated_at="2026-07-12T10:13:00Z",
        location={"lat": 14.55043, "lng": 121.07967, "course": 233, "position_time": "2026-07-12 10:13:00"},
        status={"speed": 0, "isIgnitionOn": False, "batteryLevel": -1, "isOnline": True},
        eventTriggered=None
    )

    # 1. State is identical
    state_identical = TelemetryState(
        device_id="test-device",
        timestamp="2026-07-12T10:14:00Z",
        location=LocationInfo(lat=14.55043, lng=121.07967, course=233, position_time="2026-07-12 10:13:00"),
        status=StatusInfo(speed=0, is_ignition_on=False, battery_level=-1, is_online=True)
    )
    
    curr_loc = state_identical.location.to_dict()
    curr_stat = state_identical.status.to_dict()
    has_changed_identical = (curr_loc != previous_doc.location) or (curr_stat != previous_doc.status)
    assert not has_changed_identical, "Identical state should report no changes"

    # 2. State has location change (e.g. position_time changes)
    state_with_loc_change = TelemetryState(
        device_id="test-device",
        timestamp="2026-07-12T10:14:00Z",
        location=LocationInfo(lat=14.55043, lng=121.07967, course=233, position_time="2026-07-12 10:14:00"),
        status=StatusInfo(speed=0, is_ignition_on=False, battery_level=-1, is_online=True)
    )
    
    curr_loc = state_with_loc_change.location.to_dict()
    curr_stat = state_with_loc_change.status.to_dict()
    has_changed_loc = (curr_loc != previous_doc.location) or (curr_stat != previous_doc.status)
    assert has_changed_loc, "Location change (position_time update) should report a change"

    # 3. State has status change (e.g. speed changes)
    state_with_status_change = TelemetryState(
        device_id="test-device",
        timestamp="2026-07-12T10:14:00Z",
        location=LocationInfo(lat=14.55043, lng=121.07967, course=233, position_time="2026-07-12 10:13:00"),
        status=StatusInfo(speed=5, is_ignition_on=False, battery_level=-1, is_online=True)
    )
    
    curr_loc = state_with_status_change.location.to_dict()
    curr_stat = state_with_status_change.status.to_dict()
    has_changed_status = (curr_loc != previous_doc.location) or (curr_stat != previous_doc.status)
    assert has_changed_status, "Status change (speed update) should report a change"


def test_last_checked_at_initialization():
    state = TelemetryState(
        device_id="test-device",
        timestamp="2026-07-12T10:24:00Z",
        location=LocationInfo(lat=14.55043, lng=121.07967, course=233),
        status=StatusInfo(speed=0, is_ignition_on=False, battery_level=-1, is_online=True)
    )
    doc = TelemetryDocument.from_state(state)
    assert doc.last_checked_at == "2026-07-12T10:24:00Z"
    
    serialized = doc.to_cosmos_dict()
    assert serialized["last_checked_at"] == "2026-07-12T10:24:00Z"
