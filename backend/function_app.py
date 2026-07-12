"""Antigravity — Telemetry & Event Middleware

Azure Functions v2 (Python) entry point.

Triggers:
    - Timer   : ``poll_telemetry``      — every 10 seconds
    - HTTP GET: ``get_current``         — /api/telemetry/current
    - HTTP GET: ``get_history``         — /api/telemetry/history
    - HTTP GET: ``get_events``          — /api/telemetry/events
    - HTTP GET: ``negotiate_pubsub``    — /api/pubsub/negotiate
"""

import json
import logging
import os

import azure.functions as func

from models.documents import TelemetryDocument
from services.aika_service import AikaService
from services.cosmos_service import CosmosService
from services.event_engine import compute_event
from services.broadcast_service import BroadcastService

logger = logging.getLogger(__name__)

app = func.FunctionApp()

# ====================================================================== #
#  Configuration (read once at cold-start)
# ====================================================================== #

COSMOS_CONN = os.environ.get("CosmosDBConnectionString", "")
COSMOS_DB = os.environ.get("COSMOS_DATABASE_NAME", "AntigravityDb")
COSMOS_CONTAINER = os.environ.get("COSMOS_CONTAINER_NAME", "Telemetry")

PUBSUB_CONN = os.environ.get("WebPubSubConnectionString", "")
PUBSUB_HUB = os.environ.get("WEBPUBSUB_HUB_NAME", "telemetry_hub")

AIKA_SERVER = os.environ.get("AIKA_SERVER_URL", "http://www.aika168.com/")
AIKA_DEVICE = os.environ.get("AIKA_DEVICE_ID", "")
AIKA_PASSWORD = os.environ.get("AIKA_PASSWORD", "")

ENABLE_SECURITY = os.environ.get("ENABLE_SECURITY_ALERT", "false").lower() == "true"
ENABLE_WEBPUB_BROADCAST = os.environ.get("ENABLE_WEBPUB_BROADCAST", "true").lower() == "true"
SAVE_RAW_PAYLOAD = os.environ.get("SAVE_RAW_PAYLOAD", "false").lower() == "true"
BROADCAST_ALL_POLLS = os.environ.get("BROADCAST_ALL_POLLS", "false").lower() == "true"
COMMAND_PIN = os.environ.get("COMMAND_PIN", "1234")

# ====================================================================== #
#  Lazy-initialised service singletons (reused across warm invocations)
# ====================================================================== #

_cosmos_svc: CosmosService | None = None
_broadcast_svc: BroadcastService | None = None
_aika_svc: AikaService | None = None


def _get_cosmos() -> CosmosService:
    global _cosmos_svc
    if _cosmos_svc is None:
        _cosmos_svc = CosmosService(COSMOS_CONN, COSMOS_DB, COSMOS_CONTAINER)
    return _cosmos_svc


def _get_broadcast() -> BroadcastService:
    global _broadcast_svc
    if _broadcast_svc is None:
        _broadcast_svc = BroadcastService(PUBSUB_CONN, PUBSUB_HUB)
    return _broadcast_svc


def _get_aika() -> AikaService:
    global _aika_svc
    if _aika_svc is None:
        _aika_svc = AikaService(AIKA_SERVER, AIKA_DEVICE, AIKA_PASSWORD)
    return _aika_svc


# ====================================================================== #
#  TIMER TRIGGER — Poller (every 10 seconds)
# ====================================================================== #


@app.timer_trigger(
    schedule="*/20 * * * * *",
    arg_name="mytimer",
    run_on_startup=False,
)
@app.cosmos_db_output(
    arg_name="cosmosout",
    database_name="%COSMOS_DATABASE_NAME%",
    container_name="%COSMOS_CONTAINER_NAME%",
    connection="CosmosDBConnectionString",
    create_if_not_exists=True,
    partition_key="/deviceId",
)
async def poll_telemetry(
    mytimer: func.TimerRequest,
    cosmosout: func.Out[str],
) -> None:
    """Core polling loop — see spec Section 5 (Sequence Diagram)."""

    if mytimer.past_due:
        logger.warning("Timer is past due — executing anyway.")

    try:
        # Step 1: Fetch current state from AIKA API
        aika = _get_aika()
        current_state = await aika.fetch_current_state(save_raw_payload=SAVE_RAW_PAYLOAD)

        # Step 2: Get previous state from Cosmos DB
        cosmos = _get_cosmos()
        previous_doc = await cosmos.get_previous_state(current_state.device_id)

        # Step 2.5: Inherit previous location if current is missing (0.0, 0.0)
        if current_state.location.lat == 0.0 and current_state.location.lng == 0.0 and previous_doc is not None:
            from models.telemetry import LocationInfo, TelemetryState
            current_state = TelemetryState(
                device_id=current_state.device_id,
                timestamp=current_state.timestamp,
                location=LocationInfo(
                    lat=previous_doc.location.get("lat", 0.0),
                    lng=previous_doc.location.get("lng", 0.0),
                    course=previous_doc.location.get("course", 0),
                    position_time=previous_doc.location.get("position_time")
                ),
                status=current_state.status,
                raw_payload=current_state.raw_payload
            )

        # Step 3: Compute event
        event = compute_event(current_state, previous_doc, ENABLE_SECURITY)

        # Step 4: Build document and write to Cosmos DB
        has_changed = True
        if previous_doc is not None:
            curr_loc = current_state.location.to_dict()
            curr_stat = current_state.status.to_dict()
            
            location_changed = any(
                curr_loc.get(k) != previous_doc.location.get(k)
                for k in ["lat", "lng", "course"]
            )
            status_changed = any(
                curr_stat.get(k) != previous_doc.status.get(k)
                for k in ["isIgnitionOn", "batteryLevel", "isOnline"]
            )
            has_changed = location_changed or status_changed or (event is not None)

        if has_changed:
            doc = TelemetryDocument.from_state(current_state, event)
            cosmosout.set(json.dumps(doc.to_cosmos_dict()))
            logger.info(
                "Persisted new document id=%s, event=%s",
                doc.id,
                doc.eventTriggered or "none",
            )
        else:
            previous_doc.last_checked_at = current_state.timestamp
            cosmosout.set(json.dumps(previous_doc.to_cosmos_dict()))
            logger.info(
                "Telemetry unchanged. Updated last_checked_at to %s on existing document id=%s",
                current_state.timestamp,
                previous_doc.id,
            )
            doc = previous_doc

        # Step 5: Broadcast event (if triggered, or if telemetry changed, or if broadcasting all polls is enabled)
        should_broadcast = (event is not None or has_changed or BROADCAST_ALL_POLLS)
        if should_broadcast and ENABLE_WEBPUB_BROADCAST and PUBSUB_CONN:
            broadcast = _get_broadcast()
            await broadcast.broadcast_event(doc.to_cosmos_dict())

    except Exception:
        logger.exception("Error in poll_telemetry")


# ====================================================================== #
#  HTTP TRIGGERS — REST API for frontend consumption
# ====================================================================== #


@app.function_name("get_current")
@app.route(route="telemetry/current", methods=["GET"], auth_level=func.AuthLevel.ANONYMOUS)
async def get_current(req: func.HttpRequest) -> func.HttpResponse:
    """Return the latest telemetry document for the configured device."""

    try:
        cosmos = _get_cosmos()
        doc = await cosmos.get_previous_state(AIKA_DEVICE)

        if doc is None:
            return func.HttpResponse(
                json.dumps({"error": "No telemetry data found"}),
                status_code=404,
                mimetype="application/json",
            )

        return func.HttpResponse(
            json.dumps(doc.to_cosmos_dict()),
            status_code=200,
            mimetype="application/json",
        )
    except Exception as e:
        logger.exception("Error in get_current")
        return func.HttpResponse(
            json.dumps({"error": str(e)}),
            status_code=500,
            mimetype="application/json",
        )


@app.function_name("get_history")
@app.route(route="telemetry/history", methods=["GET"], auth_level=func.AuthLevel.ANONYMOUS)
async def get_history(req: func.HttpRequest) -> func.HttpResponse:
    """Return recent telemetry history.

    Query params:
        - ``limit`` (int, default 50): max records to return
        - ``hours`` (int, default 24): time window in hours
    """

    try:
        limit = int(req.params.get("limit", "50"))
        hours = int(req.params.get("hours", "24"))

        cosmos = _get_cosmos()
        docs = await cosmos.get_history(AIKA_DEVICE, limit=limit, hours=hours)

        return func.HttpResponse(
            json.dumps([d.to_cosmos_dict() for d in docs]),
            status_code=200,
            mimetype="application/json",
        )
    except Exception as e:
        logger.exception("Error in get_history")
        return func.HttpResponse(
            json.dumps({"error": str(e)}),
            status_code=500,
            mimetype="application/json",
        )


@app.function_name("get_events")
@app.route(route="telemetry/events", methods=["GET"], auth_level=func.AuthLevel.ANONYMOUS)
async def get_events(req: func.HttpRequest) -> func.HttpResponse:
    """Return recent events (documents with non-null ``eventTriggered``).

    Query params:
        - ``limit`` (int, default 20): max events to return
    """

    try:
        limit = int(req.params.get("limit", "20"))

        cosmos = _get_cosmos()
        docs = await cosmos.get_events(AIKA_DEVICE, limit=limit)

        return func.HttpResponse(
            json.dumps([d.to_cosmos_dict() for d in docs]),
            status_code=200,
            mimetype="application/json",
        )
    except Exception as e:
        logger.exception("Error in get_events")
        return func.HttpResponse(
            json.dumps({"error": str(e)}),
            status_code=500,
            mimetype="application/json",
        )


@app.function_name("negotiate_pubsub")
@app.route(route="pubsub/negotiate", methods=["GET"], auth_level=func.AuthLevel.ANONYMOUS)
async def negotiate_pubsub(req: func.HttpRequest) -> func.HttpResponse:
    """Return a WebSocket client access URL for connection.

    The frontend calls this to get a short-lived token and WebSocket URL.
    """

    if not PUBSUB_CONN:
        return func.HttpResponse(
            json.dumps({"error": "Broadcast service not configured"}),
            status_code=503,
            mimetype="application/json",
        )

    try:
        # Extract hostname from request headers
        host_header = req.headers.get("host", "localhost")
        request_hostname = host_header.split(":")[0]

        broadcast = _get_broadcast()
        url = broadcast.get_client_access_url(request_hostname=request_hostname)

        return func.HttpResponse(
            json.dumps({
                "provider": broadcast.provider,
                "url": url
            }),
            status_code=200,
            mimetype="application/json",
        )
    except Exception as e:
        logger.exception("Error in negotiate_pubsub")
        return func.HttpResponse(
            json.dumps({"error": str(e)}),
            status_code=500,
            mimetype="application/json",
        )


@app.function_name("send_device_command")
@app.route(route="device/command", methods=["POST"], auth_level=func.AuthLevel.ANONYMOUS)
async def send_device_command(req: func.HttpRequest) -> func.HttpResponse:
    """Send a command (DY/KY) to the tracking device, protected by a PIN."""

    try:
        req_body = req.get_json()
    except ValueError:
        return func.HttpResponse(
            json.dumps({"error": "Invalid JSON body"}),
            status_code=400,
            mimetype="application/json",
        )

    command = req_body.get("command")
    pin = req_body.get("pin")

    if not command or command not in ("DY", "KY"):
        return func.HttpResponse(
            json.dumps({"error": "Invalid command. Must be 'DY' or 'KY'"}),
            status_code=400,
            mimetype="application/json",
        )

    if not pin or str(pin) != str(COMMAND_PIN):
        return func.HttpResponse(
            json.dumps({"error": "Invalid PIN"}),
            status_code=401,
            mimetype="application/json",
        )

    try:
        aika = _get_aika()
        res = await aika.send_command(command)
        return func.HttpResponse(
            json.dumps({"success": True, "result": res}),
            status_code=200,
            mimetype="application/json",
        )
    except Exception as e:
        logger.exception("Failed to send command to device")
        return func.HttpResponse(
            json.dumps({"error": f"Failed to send command: {str(e)}"}),
            status_code=500,
            mimetype="application/json",
        )

