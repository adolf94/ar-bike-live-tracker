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
from services.cloud_messaging_service import CloudMessagingService

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

ENABLE_SECURITY = os.environ.get("ENABLE_SECURITY_ALERT", "true").lower() == "true"
SAVE_RAW_PAYLOAD = os.environ.get("SAVE_RAW_PAYLOAD", "true").lower() == "true"
ENABLE_WEBPUB_BROADCAST = os.environ.get("ENABLE_WEBPUB_BROADCAST", "true").lower() == "true"
BROADCAST_ALL_POLLS = os.environ.get("BROADCAST_ALL_POLLS", "false").lower() == "true"
COMMAND_PIN = os.environ.get("COMMAND_PIN", "1236")

ENABLE_CLOUD_MESSAGING = os.environ.get("ENABLE_CLOUD_MESSAGING", "false").lower() == "true"
AUTOMATE_ENABLED = os.environ.get("AUTOMATE_ENABLED", "false").lower() == "true"
AUTOMATE_SECRET = os.environ.get("AUTOMATE_SECRET", "")
AUTOMATE_TO = os.environ.get("AUTOMATE_TO", "")
AUTOMATE_DEVICE = os.environ.get("AUTOMATE_DEVICE", "")
FCM_ENABLED = os.environ.get("FCM_ENABLED", "false").lower() == "true"
FCM_PROJECT_ID = os.environ.get("FCM_PROJECT_ID", "")
FCM_SERVICE_ACCOUNT_JSON = os.environ.get("FCM_SERVICE_ACCOUNT_JSON", "")

# ====================================================================== #
#  Lazy-initialised service singletons (reused across warm invocations)
# ====================================================================== #

_cosmos_svc: CosmosService | None = None
_broadcast_svc: BroadcastService | None = None
_aika_svc: AikaService | None = None
_cache_svc: MemoryCacheService | None = None
_cloud_messaging_svc: CloudMessagingService | None = None


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
        _cache_svc = MemoryCacheService(cosmos_service=_get_cosmos())
    return _cache_svc


def _get_cloud_messaging() -> CloudMessagingService:
    global _cloud_messaging_svc
    if _cloud_messaging_svc is None:
        _cloud_messaging_svc = CloudMessagingService.from_environment(
            automate_secret=AUTOMATE_SECRET,
            automate_to=AUTOMATE_TO,
            automate_device=AUTOMATE_DEVICE,
            fcm_project_id=FCM_PROJECT_ID,
            fcm_service_account_json=FCM_SERVICE_ACCOUNT_JSON,
            cosmos_service=_get_cosmos(),
        )
    return _cloud_messaging_svc


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

        # Step 7.5: Broadcast latest bike location to active HatidKuya delivery orders
        if final_doc and final_doc.location:
            try:
                final_loc = final_doc.location
                if final_loc.get("lat") and final_loc.get("lng"):
                    order_svc = _get_order_service()
                    # Always use valid ISO-8601 UTC string for live tracking
                    now_iso = datetime.now(timezone.utc).isoformat()
                    timestamp_val = (
                        getattr(final_doc, "status_updated_at", None)
                        or getattr(final_doc, "last_checked_at", None)
                        or now_iso
                    )
                    updated_orders = order_svc.broadcast_telemetry_to_active_orders(
                        lat=float(final_loc["lat"]),
                        lng=float(final_loc["lng"]),
                        timestamp=timestamp_val
                    )
                    if updated_orders > 0:
                        logger.info("Broadcasted telemetry GPS to %d active HatidKuya orders", updated_orders)
            except Exception as e:
                logger.warning("Error dispatching telemetry to active HatidKuya orders: %s", e)
        
        # Step 8: Send cloud notifications (if event triggered)
        if event is not None and ENABLE_CLOUD_MESSAGING:
            try:
                messaging = _get_cloud_messaging()
                success, results = await messaging.send_event_notification(
                    event_type=event,
                    telemetry_doc=final_doc,
                    user_ids=[],
                )
                
                if success:
                    logger.info(f"Cloud notifications sent for event {event.value}: {results}")
                else:
                    logger.warning(f"Cloud notifications failed for event {event.value}: {results}")
                    
            except Exception as e:
                logger.exception(f"Error sending cloud notifications: {e}")

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
    """Return recent telemetry history."""
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
    """Return recent events."""
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
    """Return a WebSocket client access URL for connection."""
    auth_err = _check_auth(req)
    if auth_err: return auth_err

    if not PUBSUB_CONN:
        return func.HttpResponse(
            json.dumps({"error": "Broadcast service not configured"}),
            status_code=503,
            mimetype="application/json",
        )

    try:
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
#  Device Token Registration Endpoints (FCM)
# ====================================================================== #

@app.function_name("register_device_token")
@app.route(route="devices/register-token", methods=["POST"], auth_level=func.AuthLevel.ANONYMOUS)
async def register_device_token(req: func.HttpRequest) -> func.HttpResponse:
    """Register or update an FCM device token for the authenticated user."""
    auth_error = _check_auth(req)
    if auth_error:
        return auth_error
    
    try:
        payload = req.get_json()
    except ValueError:
        return func.HttpResponse(
            '{"error": "Invalid JSON"}',
            status_code=400,
            mimetype="application/json",
        )
    
    fcm_token = payload.get("fcmToken")
    platform = payload.get("platform", "android")
    
    if not fcm_token:
        return func.HttpResponse(
            '{"error": "Missing \"fcmToken\" field"}',
            status_code=400,
            mimetype="application/json",
        )
    
    try:
        from services.auth_service import decode_token
        auth_header = req.headers.get("Authorization", "")
        token = auth_header.replace("Bearer ", "")
        claims = decode_token(token)
        user_id = claims.get("sub") or claims.get("oid") or "unknown"
    except Exception as e:
        logger.error(f"Failed to extract user ID from token: {e}")
        return func.HttpResponse(
            '{"error": "Invalid authentication token"}',
            status_code=401,
            mimetype="application/json",
        )
    
    try:
        cosmos = _get_cosmos()
        success = await cosmos.register_device_token(user_id, fcm_token, platform)
        
        if success:
            return func.HttpResponse(
                json.dumps({"success": True, "message": "Device token registered"}),
                status_code=200,
                mimetype="application/json",
            )
        else:
            return func.HttpResponse(
                json.dumps({"success": False, "error": "Failed to register token"}),
                status_code=500,
                mimetype="application/json",
            )
            
    except Exception as e:
        logger.exception(f"Error registering device token: {e}")
        return func.HttpResponse(
            json.dumps({"error": str(e)}),
            status_code=500,
            mimetype="application/json",
        )


@app.function_name("unregister_device_token")
@app.route(route="devices/register-token", methods=["DELETE"], auth_level=func.AuthLevel.ANONYMOUS)
async def unregister_device_token(req: func.HttpRequest) -> func.HttpResponse:
    """Unregister an FCM device token for the authenticated user."""
    auth_error = _check_auth(req)
    if auth_error:
        return auth_error
    
    try:
        payload = req.get_json()
    except ValueError:
        return func.HttpResponse(
            '{"error": "Invalid JSON"}',
            status_code=400,
            mimetype="application/json",
        )
    
    fcm_token = payload.get("fcmToken")
    
    if not fcm_token:
        return func.HttpResponse(
            '{"error": "Missing \"fcmToken\" field"}',
            status_code=400,
            mimetype="application/json",
        )
    
    try:
        from services.auth_service import decode_token
        auth_header = req.headers.get("Authorization", "")
        token = auth_header.replace("Bearer ", "")
        claims = decode_token(token)
        user_id = claims.get("sub") or claims.get("oid") or "unknown"
    except Exception as e:
        logger.error(f"Failed to extract user ID from token: {e}")
        return func.HttpResponse(
            '{"error": "Invalid authentication token"}',
            status_code=401,
            mimetype="application/json",
        )
    
    try:
        cosmos = _get_cosmos()
        success = await cosmos.unregister_device_token(user_id, fcm_token)
        
        if success:
            return func.HttpResponse(
                json.dumps({"success": True, "message": "Device token unregistered"}),
                status_code=200,
                mimetype="application/json",
            )
        else:
            return func.HttpResponse(
                json.dumps({"success": False, "error": "Token not found or failed to unregister"}),
                status_code=404,
                mimetype="application/json",
            )
            
    except Exception as e:
        logger.exception(f"Error unregistering device token: {e}")
        return func.HttpResponse(
            json.dumps({"error": str(e)}),
            status_code=500,
            mimetype="application/json",
        )


# ====================================================================== #
#  HTTP TRIGGER — Health Check
# ====================================================================== #


@app.function_name("health")
@app.route(route="health", methods=["GET"], auth_level=func.AuthLevel.ANONYMOUS)
async def health(req: func.HttpRequest) -> func.HttpResponse:
    """Liveness + dependency health check."""
    import datetime

    services: dict[str, dict] = {}

    try:
        cosmos = _get_cosmos()
        await cosmos.get_previous_state(AIKA_DEVICE)
        services["cosmos"] = {"ok": True, "detail": "reachable"}
    except Exception as exc:
        services["cosmos"] = {"ok": False, "detail": str(exc)}

    try:
        if not PUBSUB_CONN:
            services["broadcast"] = {"ok": False, "detail": "not configured"}
        else:
            broadcast = _get_broadcast()
            provider = broadcast.provider
            services["broadcast"] = {"ok": True, "detail": f"provider={provider}"}
    except Exception as exc:
        services["broadcast"] = {"ok": False, "detail": str(exc)}

    try:
        if not AIKA_DEVICE or not AIKA_PASSWORD:
            services["aika"] = {"ok": False, "detail": "credentials not configured"}
        else:
            aika = _get_aika()
            await aika.fetch_current_state(save_raw_payload=False)
            services["aika"] = {"ok": True, "detail": "reachable"}
    except Exception as exc:
        services["aika"] = {"ok": False, "detail": str(exc)}
    
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


# ====================================================================== #
#  HTTP TRIGGER — HatidKuya Delivery Endpoints
# ====================================================================== #

_order_service = None
_signalr_pub = None


def _get_order_service() -> "OrderService":
    global _order_service
    if _order_service is None:
        from services.order_service import OrderService
        _order_service = OrderService()
    return _order_service


def _get_signalr_pub() -> "SignalRPublisher":
    global _signalr_pub
    if _signalr_pub is None:
        from services.signalr_publisher import SignalRPublisher
        _signalr_pub = SignalRPublisher()
    return _signalr_pub


def _json_cors_response(data: any, status_code: int = 200) -> func.HttpResponse:
    return func.HttpResponse(
        body=json.dumps(data),
        status_code=status_code,
        mimetype="application/json",
        headers={
            "Access-Control-Allow-Origin": "*",
            "Access-Control-Allow-Methods": "GET, POST, OPTIONS",
            "Access-Control-Allow-Headers": "Content-Type, Authorization",
        },
    )


@app.function_name("create_order")
@app.route(route="orders", methods=["POST", "OPTIONS"], auth_level=func.AuthLevel.ANONYMOUS)
async def create_order(req: func.HttpRequest) -> func.HttpResponse:
    if req.method == "OPTIONS":
        return _json_cors_response({}, 200)
    try:
        from models.order import CreateOrderRequest
        body = req.get_json()
        order_req = CreateOrderRequest(**body)

        # Retrieve latest known bike location directly from Cosmos DB / poll_telemetry cache
        initial_loc = None
        try:
            cosmos = _get_cosmos()
            latest_doc = await cosmos.get_previous_state(AIKA_DEVICE)
            if not latest_doc:
                cache = _get_cache()
                latest_doc = await cache.get_latest()

            if latest_doc and latest_doc.location:
                lat_val = latest_doc.location.get("lat")
                lng_val = latest_doc.location.get("lng")
                if lat_val and lng_val and lat_val != 0.0 and lng_val != 0.0:
                    initial_loc = {
                        "lat": float(lat_val),
                        "lng": float(lng_val),
                        "timestamp": latest_doc.timestamp or latest_doc.location.get("position_time")
                    }
                    logger.info("Seeded new order with latest DB telemetry location: %s, %s", lat_val, lng_val)
        except Exception as err:
            logger.warning("Could not retrieve latest bike telemetry from DB for order: %s", err)

        result = _get_order_service().create_order(order_req, initial_location=initial_loc)
        return _json_cors_response(result, status_code=201)
    except Exception as e:
        logger.exception("Error creating order: %s", e)
        return _json_cors_response({"error": str(e)}, status_code=400)


@app.function_name("get_active_order")
@app.route(route="orders/active", methods=["GET", "OPTIONS"], auth_level=func.AuthLevel.ANONYMOUS)
def get_active_order(req: func.HttpRequest) -> func.HttpResponse:
    if req.method == "OPTIONS":
        return _json_cors_response({}, 200)
    try:
        active_order = _get_order_service().get_latest_active_order()
        return _json_cors_response(active_order, status_code=200)
    except Exception as e:
        logger.exception("Error getting active order: %s", e)
        return _json_cors_response(None, status_code=200)


@app.function_name("get_order")
@app.route(route="orders/{trackingId}", methods=["GET", "OPTIONS"], auth_level=func.AuthLevel.ANONYMOUS)
async def get_order(req: func.HttpRequest) -> func.HttpResponse:
    if req.method == "OPTIONS":
        return _json_cors_response({}, 200)
    tracking_id = req.route_params.get("trackingId")
    if not tracking_id:
        return _json_cors_response({"error": "trackingId is required"}, status_code=400)

    order = _get_order_service().get_order_by_tracking_id(tracking_id)
    if not order:
        return _json_cors_response({"error": "Order not found"}, status_code=404)

    # If last_location is not yet set on the order, attach the cached latest bike location
    if not order.get("last_location"):
        try:
            cache = _get_cache()
            latest_doc = await cache.get_latest()
            if not latest_doc:
                cosmos = _get_cosmos()
                latest_doc = await cosmos.get_previous_state(AIKA_DEVICE)
            if latest_doc and latest_doc.location:
                ts_val = (
                    latest_doc.location.get("position_time")
                    or getattr(latest_doc, "status_updated_at", None)
                    or getattr(latest_doc, "last_checked_at", None)
                    or datetime.now(timezone.utc).isoformat()
                )
                order["last_location"] = {
                    "lat": latest_doc.location.get("lat"),
                    "lng": latest_doc.location.get("lng"),
                    "timestamp": ts_val,
                    "source": "poll_telemetry"
                }
        except Exception as e:
            logger.warning("Error resolving latest cached location for get_order: %s", e)

    return _json_cors_response(order, status_code=200)


@app.function_name("update_order_location")
@app.route(route="orders/{orderId}/location", methods=["POST", "OPTIONS"], auth_level=func.AuthLevel.ANONYMOUS)
def update_order_location(req: func.HttpRequest) -> func.HttpResponse:
    if req.method == "OPTIONS":
        return _json_cors_response({}, 200)
    order_id = req.route_params.get("orderId")
    if not order_id:
        return _json_cors_response({"error": "orderId is required"}, status_code=400)

    try:
        from models.order import UpdateLocationRequest
        body = req.get_json()
        loc_req = UpdateLocationRequest(**body)
        updated = _get_order_service().update_location(order_id, loc_req)
        if not updated:
            return _json_cors_response({"error": "Order not found"}, status_code=404)
        return _json_cors_response(updated, status_code=200)
    except Exception as e:
        logger.exception("Error updating location: %s", e)
        return _json_cors_response({"error": str(e)}, status_code=400)


@app.function_name("update_order_stage")
@app.route(route="orders/{orderId}/stage", methods=["POST", "OPTIONS"], auth_level=func.AuthLevel.ANONYMOUS)
def update_order_stage(req: func.HttpRequest) -> func.HttpResponse:
    if req.method == "OPTIONS":
        return _json_cors_response({}, 200)
    order_id = req.route_params.get("orderId")
    if not order_id:
        return _json_cors_response({"error": "orderId is required"}, status_code=400)

    try:
        body = req.get_json()
        stage = body.get("stage") or body.get("delivery_stage") or "going_to_pickup"
        updated = _get_order_service().update_delivery_stage(order_id, stage)
        if not updated:
            return _json_cors_response({"error": "Order not found"}, status_code=404)
        return _json_cors_response(updated, status_code=200)
    except Exception as e:
        logger.exception("Error updating delivery stage: %s", e)
        return _json_cors_response({"error": str(e)}, status_code=400)


@app.function_name("complete_order")
@app.route(route="orders/{orderId}/complete", methods=["POST", "OPTIONS"], auth_level=func.AuthLevel.ANONYMOUS)
def complete_order(req: func.HttpRequest) -> func.HttpResponse:
    if req.method == "OPTIONS":
        return _json_cors_response({}, 200)
    order_id = req.route_params.get("orderId")
    if not order_id:
        return _json_cors_response({"error": "orderId is required"}, status_code=400)

    try:
        updated = _get_order_service().complete_order(order_id)
        if not updated:
            return _json_cors_response({"error": "Order not found"}, status_code=404)
        return _json_cors_response(updated, status_code=200)
    except Exception as e:
        logger.exception("Error completing order: %s", e)
        return _json_cors_response({"error": str(e)}, status_code=400)


@app.function_name("search_locations")
@app.route(route="locations/search", methods=["GET", "OPTIONS"], auth_level=func.AuthLevel.ANONYMOUS)
def search_locations(req: func.HttpRequest) -> func.HttpResponse:
    if req.method == "OPTIONS":
        return _json_cors_response({}, 200)
    query = req.params.get("q")
    if not query or len(query.strip()) < 2:
        return _json_cors_response([], status_code=200)

    google_api_key = os.environ.get("GOOGLE_MAPS_API_KEY", "").strip()

    # 1. Primary: Google Places Autocomplete (if API key is present)
    if google_api_key:
        try:
            import requests
            google_url = "https://maps.googleapis.com/maps/api/place/autocomplete/json"
            params = {
                "input": query.strip(),
                "key": google_api_key,
                "components": "country:ph",
                "location": "14.5995,120.9842",  # Metro Manila bias
                "radius": "50000",
                "language": "en"
            }
            res = requests.get(google_url, params=params, timeout=5)
            if res.status_code == 200:
                data = res.json()
                predictions = data.get("predictions", [])
                results = []
                for p in predictions[:6]:
                    place_id = p.get("place_id")
                    desc = p.get("description", "")
                    main_text = p.get("structured_formatting", {}).get("main_text", desc)
                    results.append({
                        "place_id": place_id,
                        "name": main_text,
                        "display_name": desc,
                        "lat": 0,
                        "lon": 0
                    })

                if results:
                    return _json_cors_response(results, status_code=200)
        except Exception as e:
            logger.warning("Google Maps search error, falling back: %s", e)

    # 2. Fallback: Photon (OpenStreetMap Elasticsearch)
    try:
        import requests
        headers = {
            "User-Agent": "HatidKuyaDeliveryApp/1.0",
            "Accept-Language": "en"
        }
        photon_url = "https://photon.komoot.io/api/"
        params = {
            "q": query.strip(),
            "limit": 6,
            "lat": 14.5995,
            "lon": 120.9842
        }
        res = requests.get(photon_url, params=params, headers=headers, timeout=4)
        if res.status_code == 200:
            data = res.json()
            features = data.get("features", [])
            results = []
            for f in features:
                props = f.get("properties", {})
                coords = f.get("geometry", {}).get("coordinates", [0, 0])
                name = props.get("name") or props.get("street") or query
                parts = [props.get("name"), props.get("street"), props.get("city"), props.get("state"), props.get("country")]
                address = ", ".join([p for p in parts if p])
                results.append({
                    "name": name,
                    "display_name": address or name,
                    "lat": coords[1],
                    "lon": coords[0]
                })
            if results:
                return _json_cors_response(results, status_code=200)

        # 3. Fallback: OpenStreetMap Nominatim
        nom_url = "https://nominatim.openstreetmap.org/search"
        nom_params = {
            "q": query.strip(),
            "format": "json",
            "addressdetails": 1,
            "limit": 6,
            "countrycodes": "ph"
        }
        nom_res = requests.get(nom_url, params=nom_params, headers=headers, timeout=4)
        return _json_cors_response(nom_res.json(), status_code=200)

    except Exception as e:
        logger.exception("Error searching location: %s", e)
        return _json_cors_response([], status_code=200)


@app.function_name("get_location_details")
@app.route(route="locations/details", methods=["GET", "OPTIONS"], auth_level=func.AuthLevel.ANONYMOUS)
def get_location_details(req: func.HttpRequest) -> func.HttpResponse:
    if req.method == "OPTIONS":
        return _json_cors_response({}, 200)

    place_id = req.params.get("place_id")
    address = req.params.get("address")
    google_api_key = os.environ.get("GOOGLE_MAPS_API_KEY", "").strip()

    lat, lng = 14.5995, 120.9842

    if google_api_key:
        try:
            import requests
            if place_id:
                details_url = "https://maps.googleapis.com/maps/api/place/details/json"
                d_res = requests.get(details_url, params={"place_id": place_id, "fields": "geometry,formatted_address", "key": google_api_key}, timeout=4)
                if d_res.status_code == 200:
                    data = d_res.json().get("result", {})
                    geom = data.get("geometry", {}).get("location", {})
                    if geom.get("lat") and geom.get("lng"):
                        return _json_cors_response({
                            "lat": geom["lat"],
                            "lng": geom["lng"],
                            "address": data.get("formatted_address") or address or ""
                        }, status_code=200)
            elif address:
                geo_url = "https://maps.googleapis.com/maps/api/geocode/json"
                g_res = requests.get(geo_url, params={"address": address, "components": "country:ph", "key": google_api_key}, timeout=4)
                if g_res.status_code == 200:
                    results = g_res.json().get("results", [])
                    if results:
                        geom = results[0].get("geometry", {}).get("location", {})
                        return _json_cors_response({
                            "lat": geom.get("lat", lat),
                            "lng": geom.get("lng", lng),
                            "address": results[0].get("formatted_address") or address
                        }, status_code=200)
        except Exception as e:
            logger.warning("Error fetching Google Place details: %s", e)

    return _json_cors_response({"lat": lat, "lng": lng, "address": address or ""}, status_code=200)


@app.function_name("negotiate_order_signalr")
@app.route(route="negotiate/{trackingId}", methods=["POST", "OPTIONS"], auth_level=func.AuthLevel.ANONYMOUS)
def negotiate_order_signalr(req: func.HttpRequest) -> func.HttpResponse:
    if req.method == "OPTIONS":
        return _json_cors_response({}, 200)
    tracking_id = req.route_params.get("trackingId")
    if not tracking_id:
        return _json_cors_response({"error": "trackingId is required"}, status_code=400)

    try:
        negotiation = _get_signalr_pub().negotiate(tracking_id)
        return _json_cors_response(negotiation, status_code=200)
    except Exception as e:
        logger.exception("Error negotiating SignalR token: %s", e)
        return _json_cors_response({"error": str(e)}, status_code=500)


@app.function_name("get_order_history")
@app.route(route="orders/{trackingId}/history", methods=["GET", "OPTIONS"], auth_level=func.AuthLevel.ANONYMOUS)
def get_order_history(req: func.HttpRequest) -> func.HttpResponse:
    if req.method == "OPTIONS":
        return _json_cors_response({}, 200)
    tracking_id = req.route_params.get("trackingId")
    if not tracking_id:
        return _json_cors_response({"error": "trackingId is required"}, status_code=400)

    try:
        history = _get_order_service().get_order_history(tracking_id)
        return _json_cors_response(history, status_code=200)
    except Exception as e:
        logger.exception("Error fetching order location history: %s", e)
        return _json_cors_response({"error": str(e)}, status_code=500)

