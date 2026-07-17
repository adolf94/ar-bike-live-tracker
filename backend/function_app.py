"""Antigravity — Telemetry & Event Middleware

Azure Functions v2 (Python) entry point.

Triggers:
    - Timer   : ``poll_telemetry``      — every 10 seconds
    - HTTP GET: ``get_current``         — /api/telemetry/current
    - HTTP GET: ``get_history``         — /api/telemetry/history
    - HTTP GET: ``get_events``          — /api/telemetry/events
    - HTTP GET: ``negotiate_pubsub``    — /api/pubsub/negotiate
    - HTTP GET: ``health``              — /api/health
"""

import json
import logging
import os
from datetime import datetime, timezone, timedelta

import azure.functions as func

from models.documents import TelemetryDocument
from services.aika_service import AikaService
from services.cosmos_service import CosmosService
from services.event_engine import compute_event
from services.broadcast_service import BroadcastService
from services.auth_service import verify_token
from services.memory_cache_service import MemoryCacheService

logger = logging.getLogger(__name__)

app = func.FunctionApp()

# ====================================================================== #
#  Configuration (read once at cold-start)
# ====================================================================== #

COSMOS_CONN = os.environ.get("CosmosDBConnectionString", "")
COSMOS_ENDPOINT = os.environ.get("CosmosDBEndpoint", "")
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
_cache_svc: MemoryCacheService | None = None


def _get_cosmos() -> CosmosService:
    global _cosmos_svc
    if _cosmos_svc is None:
        _cosmos_svc = CosmosService(
            connection_string=COSMOS_CONN,
            endpoint=COSMOS_ENDPOINT,
            database_name=COSMOS_DB,
            container_name=COSMOS_CONTAINER
        )
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


def _get_cache() -> MemoryCacheService:
    global _cache_svc
    if _cache_svc is None:
        _cache_svc = MemoryCacheService(_get_cosmos())
    return _cache_svc


# ====================================================================== #
#  TIMER TRIGGER — Poller (every 20 seconds)
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

        # Step 4: Determine if we need to save and update cache
        has_changed = True
        has_speed_or_time_update = False
        should_save_to_cosmos = False
        doc_to_save = None
        final_doc = None
        
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
        
        # Determine if we need to update last_checked_at due to 20-minute threshold
        should_update_last_checked = False
        if previous_doc is not None and previous_doc.last_checked_at:
            try:
                last_checked = datetime.fromisoformat(previous_doc.last_checked_at.replace('Z', '+00:00'))
                time_since_last_check = datetime.now(timezone.utc) - last_checked
                should_update_last_checked = time_since_last_check >= timedelta(minutes=20)
            except (ValueError, AttributeError):
                # If parsing fails, update anyway
                should_update_last_checked = True
        
        if has_changed:
            # Create new document for significant changes
            doc = TelemetryDocument.from_state(current_state, event)
            doc_to_save = doc
            final_doc = doc
            should_save_to_cosmos = True
            logger.info(
                "Persisted new document id=%s, event=%s",
                doc.id,
                doc.eventTriggered or "none",
            )
        else:
            # No significant changes - handle speed/time updates and 20-minute check
            if previous_doc is not None:
                curr_loc = current_state.location.to_dict()
                curr_stat = current_state.status.to_dict()
                
                speed_changed = curr_stat.get("speed") != previous_doc.status.get("speed")
                position_time_changed = curr_loc.get("position_time") != previous_doc.location.get("position_time")
                
                if speed_changed:
                    previous_doc.status["speed"] = curr_stat.get("speed")
                if position_time_changed:
                    previous_doc.location["position_time"] = curr_loc.get("position_time")
                
                has_speed_or_time_update = speed_changed or position_time_changed
            
            # Update last_checked_at
            if previous_doc is not None:
                previous_doc.last_checked_at = current_state.timestamp
                final_doc = previous_doc
                
                # Save to CosmosDB if speed/time updated OR 20-minute threshold reached
                if has_speed_or_time_update or should_update_last_checked:
                    doc_to_save = final_doc
                    should_save_to_cosmos = True
                    logger.info(
                        "Updating existing document id=%s (speed/time update or 20-min threshold)",
                        final_doc.id,
                    )
                else:
                    logger.info(
                        "Telemetry unchanged, caching only (no CosmosDB write)",
                    )
            else:
                # First poll - no previous document, create new one
                doc = TelemetryDocument.from_state(current_state, event)
                doc_to_save = doc
                final_doc = doc
                should_save_to_cosmos = True
                logger.info(
                    "First poll, creating initial document id=%s",
                    doc.id,
                )
        
        # Step 5: Save to CosmosDB if needed
        if should_save_to_cosmos and doc_to_save is not None:
            cosmosout.set(json.dumps(doc_to_save.to_cosmos_dict()))
        
        # Step 6: Update cache with latest document (whether saved or not)
        if final_doc is not None:
            cache = _get_cache()
            await cache.set_latest(final_doc)
        
        # Step 7: Broadcast event
        should_broadcast = (event is not None or has_changed or BROADCAST_ALL_POLLS or has_speed_or_time_update)
        if should_broadcast and ENABLE_WEBPUB_BROADCAST and PUBSUB_CONN:
            broadcast = _get_broadcast()
            await broadcast.broadcast_event(final_doc.to_cosmos_dict())

    except Exception:
        logger.exception("Error in poll_telemetry")


# ====================================================================== #
#  HTTP TRIGGERS — REST API for frontend consumption
# ====================================================================== #

def _check_auth(req: func.HttpRequest) -> func.HttpResponse | None:
    try:
        verify_token(req.headers.get("Authorization"))
        return None
    except ValueError as e:
        return func.HttpResponse(
            "",
            status_code=401,
            headers={"X-Auth-Reason": str(e)}
        )



@app.function_name("get_current")
@app.route(route="telemetry/current", methods=["GET"], auth_level=func.AuthLevel.ANONYMOUS)
async def get_current(req: func.HttpRequest) -> func.HttpResponse:
    """Return the latest telemetry document for the configured device."""
    auth_err = _check_auth(req)
    if auth_err: return auth_err

    try:
        # Use cache-first approach
        cache = _get_cache()
        doc = await cache.get_previous_state(AIKA_DEVICE)

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
    auth_err = _check_auth(req)
    if auth_err: return auth_err

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
    auth_err = _check_auth(req)
    if auth_err: return auth_err

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
    auth_err = _check_auth(req)
    if auth_err: return auth_err

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
    auth_err = _check_auth(req)
    if auth_err: return auth_err

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
            status_code=403,
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


# ====================================================================== #
#  HTTP TRIGGER — Health Check
# ====================================================================== #


@app.function_name("health")
@app.route(route="health", methods=["GET"], auth_level=func.AuthLevel.ANONYMOUS)
async def health(req: func.HttpRequest) -> func.HttpResponse:
    """Liveness + dependency health check.

    Returns 200 when all services are reachable, 503 when any is degraded.

    Response body:
    {
        "status": "healthy" | "degraded",
        "services": {
            "cosmos":    {"ok": bool, "detail": str},
            "broadcast": {"ok": bool, "detail": str},
            "aika":      {"ok": bool, "detail": str},
            "cache":     {"ok": bool, "detail": str, "has_data": bool}
        }
    }
    """
    import datetime

    services: dict[str, dict] = {}

    # --- Cosmos DB ---
    try:
        cosmos = _get_cosmos()
        # A lightweight call: fetch latest doc for the configured device
        await cosmos.get_previous_state(AIKA_DEVICE)
        services["cosmos"] = {"ok": True, "detail": "reachable"}
    except Exception as exc:
        services["cosmos"] = {"ok": False, "detail": str(exc)}

    # --- Broadcast service (Web PubSub / SignalR) ---
    try:
        if not PUBSUB_CONN:
            services["broadcast"] = {"ok": False, "detail": "not configured"}
        else:
            broadcast = _get_broadcast()
            # Validate the service is initialised and has a known provider
            provider = broadcast.provider
            services["broadcast"] = {"ok": True, "detail": f"provider={provider}"}
    except Exception as exc:
        services["broadcast"] = {"ok": False, "detail": str(exc)}

    # --- Aika tracker API ---
    try:
        if not AIKA_DEVICE or not AIKA_PASSWORD:
            services["aika"] = {"ok": False, "detail": "credentials not configured"}
        else:
            aika = _get_aika()
            await aika.fetch_current_state(save_raw_payload=False)
            services["aika"] = {"ok": True, "detail": "reachable"}
    except Exception as exc:
        services["aika"] = {"ok": False, "detail": str(exc)}
    
    # --- Cache service ---
    try:
        cache = _get_cache()
        cache_status = cache.get_cache_status()
        services["cache"] = {
            "ok": True, 
            "detail": "initialized",
            "has_data": cache_status["has_data"],
            "device_id": cache_status["device_id"],
            "timestamp": cache_status["timestamp"]
        }
    except Exception as exc:
        services["cache"] = {"ok": False, "detail": str(exc), "has_data": False}

    all_ok = all(s["ok"] for s in services.values())
    status_code = 200 if all_ok else 503

    body = {
        "status": "healthy" if all_ok else "degraded",
        "timestamp": datetime.datetime.utcnow().isoformat() + "Z",
        "services": services,
    }

    return func.HttpResponse(
        json.dumps(body),
        status_code=status_code,
        mimetype="application/json",
    )

