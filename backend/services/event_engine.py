"""Pure event computation logic — no I/O, fully unit-testable.

Implements the Event Engineering Logic from spec Section 4.
"""

import logging
from typing import Optional

from models.documents import TelemetryDocument
from models.telemetry import EventType, TelemetryState

logger = logging.getLogger(__name__)

# Speed threshold to distinguish parked vs. moving (km/h)
SPEED_THRESHOLD = 5.0


def compute_event(
    current: TelemetryState,
    previous: Optional[TelemetryDocument],
    enable_security_alert: bool = False,
) -> Optional[EventType]:
    """Compare current state against the previous state and determine
    whether an event should be broadcasted.

    Returns ``None`` when the poll is routine (no state transition).

    Priority order (first match wins):
        1. ``unauthorized_movement`` (if flag enabled)
        2. ``conn_lost``
        3. ``conn_restore``
        4. ``movement_started``
        5. ``movement_stopped``

    Args:
        current: The freshly-polled telemetry snapshot.
        previous: The most-recent Cosmos DB document, or ``None`` if this
            is the very first poll.
        enable_security_alert: Whether the ``unauthorized_movement`` event
            type is active.

    Returns:
        The detected ``EventType``, or ``None``.
    """

    cur_speed = current.status.speed
    cur_ignition = current.status.is_ignition_on
    cur_online = current.status.is_online

    # First poll ever — no previous state to compare against
    if previous is None:
        logger.info("No previous state found — skipping event computation.")
        return None

    prev_speed = previous.speed
    prev_ignition = previous.is_ignition_on
    prev_online = previous.is_online

    # ------------------------------------------------------------------ #
    #  4.3 — Security Alert (optional, highest priority)
    # ------------------------------------------------------------------ #
    if enable_security_alert:
        if cur_speed > SPEED_THRESHOLD and not cur_ignition:
            logger.warning(
                "UNAUTHORIZED MOVEMENT detected — speed=%.1f, ignition=OFF",
                cur_speed,
            )
            return EventType.UNAUTHORIZED_MOVEMENT

    # ------------------------------------------------------------------ #
    #  Connection Lost
    # ------------------------------------------------------------------ #
    if not cur_online and prev_online:
        logger.warning("CONN LOST — device went offline")
        return EventType.CONN_LOST

    # ------------------------------------------------------------------ #
    #  Connection Restored
    # ------------------------------------------------------------------ #
    if cur_online and not prev_online:
        logger.info("CONN RESTORE — device came back online")
        return EventType.CONN_RESTORE

    # ------------------------------------------------------------------ #
    #  4.1 — Movement Started
    # ------------------------------------------------------------------ #
    speed_started = cur_speed > SPEED_THRESHOLD and prev_speed <= SPEED_THRESHOLD
    ignition_started = cur_ignition and not prev_ignition

    if speed_started or ignition_started:
        logger.info(
            "MOVEMENT STARTED — speed %.1f→%.1f, ignition %s→%s",
            prev_speed,
            cur_speed,
            prev_ignition,
            cur_ignition,
        )
        return EventType.MOVEMENT_STARTED

    # ------------------------------------------------------------------ #
    #  4.2 — Engine Off
    # ------------------------------------------------------------------ #
    if not cur_ignition and prev_ignition:
        logger.info(
            "ENGINE OFF — ignition %s→%s",
            prev_ignition,
            cur_ignition,
        )
        return EventType.ENGINE_OFF

    # ------------------------------------------------------------------ #
    #  4.3 — Movement Stopped
    # ------------------------------------------------------------------ #
    if cur_speed == 0 and prev_speed > 0:
        logger.info(
            "MOVEMENT STOPPED — speed %.1f→%.1f",
            prev_speed,
            cur_speed,
        )
        return EventType.MOVEMENT_STOPPED

    # Routine poll — no event
    return None
