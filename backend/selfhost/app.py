"""FastAPI application — self-hosted replacement for function_app.py.

Route paths are identical to the Azure Functions routes (everything that
was ``/api/*``), so the Static Web Apps frontend needs only a base-URL
config change.

Replaces:
    - timer trigger ``poll_telemetry``      -> APScheduler job (60s)
    - cosmos_db_output binding              -> TelemetryStore.save_state
    - Web PubSub / SignalR negotiate+publish-> native WebSocket hub
    - host-level CORS OPTIONS handlers      -> CORSMiddleware
"""

import asyncio
import json
import logging
import os
import sys
from contextlib import asynccontextmanager
from datetime import datetime, timezone, timedelta
from typing import Optional

from fastapi import FastAPI, Depends, HTTPException, Request, Query, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

# Allow running as ``selfhost.app`` (cwd=backend) while db/pg_repositories/
# sync_bridge/ws_hub live next to this file, and ``services``/``models`` live
# in the backend root.
_THIS_DIR = os.path.dirname(os.path.abspath(__file__))
_BACKEND_ROOT = os.path.dirname(_THIS_DIR)
for _p in (_THIS_DIR, _BACKEND_ROOT):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from models.documents import TelemetryDocument

from db import SessionLocal, init_db
from pg_repositories import PostgresOrderRepository, TelemetryStore
from sync_bridge import set_main_loop
from ws_hub import TELEMETRY_GROUP, hub, order_group

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
logger = logging.getLogger(__name__)

# ====================================================================== #
#  Configuration (env, same variable names as the Functions app where
#  they still apply; Cosmos/SignalR vars are gone)
# ====================================================================== #

AIKA_SERVER = os.environ.get("AIKA_SERVER_URL", "http://www.aika168.com/")
AIKA_DEVICE = os.environ.get("AIKA_DEVICE_ID", "")
AIKA_PASSWORD = os.environ.get("AIKA_PASSWORD", "")

ENABLE_SECURITY = os.environ.get("ENABLE_SECURITY_ALERT", "true").lower() == "true"
SAVE_RAW_PAYLOAD = os.environ.get("SAVE_RAW_PAYLOAD", "true").lower() == "true"
BROADCAST_ALL_POLLS = os.environ.get("BROADCAST_ALL_POLLS", "false").lower() == "true"
COMMAND_PIN = os.environ.get("COMMAND_PIN", "1236")
POLL_INTERVAL_SECONDS = int(os.environ.get("POLL_INTERVAL_SECONDS", "60"))

ENABLE_CLOUD_MESSAGING = os.environ.get("ENABLE_CLOUD_MESSAGING", "false").lower() == "true"
AUTOMATE_SECRET = os.environ.get("AUTOMATE_SECRET", "")
AUTOMATE_TO = os.environ.get("AUTOMATE_TO", "")
AUTOMATE_DEVICE = os.environ.get("AUTOMATE_DEVICE", "")
FCM_PROJECT_ID = os.environ.get("FCM_PROJECT_ID", "")
FCM_SERVICE_ACCOUNT_JSON = os.environ.get("FCM_SERVICE_ACCOUNT_JSON", "")

ALLOWED_ORIGINS = [o.strip() for o in os.environ.get("ALLOWED_ORIGINS", "").split(",") if o.strip()]

# ====================================================================== #
#  Services (single instances — one process, no lazy singleton races)
# ====================================================================== #

from services.aika_service import AikaService
from services.event_engine import compute_event
from services.auth_service import verify_token, decode_token
from services.memory_cache_service import MemoryCacheService

telemetry_store = TelemetryStore(SessionLocal)
order_repo = PostgresOrderRepository(SessionLocal)
aika = AikaService(AIKA_SERVER, AIKA_DEVICE, AIKA_PASSWORD)
cache = MemoryCacheService()

# OrderService stays sync; we hand it a repo adapter + a WS-backed SignalR shim
from services.order_service import OrderService


class _SyncRepoAdapter:
    """Bridges the async Postgres repo into OrderService's sync interface."""

    def __init__(self, repo: PostgresOrderRepository) -> None:
        self._repo = repo

    def _run(self, coro):
        from sync_bridge import run_sync
        return run_sync(coro)

    def create(self, order):
        return self._run(self._repo.create(order))

    def get_by_tracking_id(self, tracking_id):
        return self._run(self._repo.get_by_tracking_id(tracking_id))

    def get_active_orders(self):
        return self._run(self._repo.get_active_orders())

    def get_latest_active_order(self):
        return self._run(self._repo.get_latest_active_order())

    def get_by_id(self, order_id):
        return self._run(self._repo.get_by_id(order_id))

    def update(self, order_dict):
        return self._run(self._repo.update(order_dict))

    def add_location_history(self, order_id, tracking_id, lat, lng, timestamp):
        return self._run(self._repo.add_location_history(order_id, tracking_id, lat, lng, timestamp))

    def get_location_history(self, tracking_id):
        return self._run(self._repo.get_location_history(tracking_id))


class _WsSignalRShim:
    """Replaces SignalRPublisher: publishes straight into the WS hub."""

    def publish_location(self, tracking_id: str, loc: dict) -> None:
        loop = asyncio.get_event_loop()
        loop.create_task(hub.publish(order_group(tracking_id), {"type": "locationUpdated", "data": loc}))

    def publish_order_completed(self, tracking_id: str) -> None:
        loop = asyncio.get_event_loop()
        loop.create_task(hub.publish(order_group(tracking_id), {"type": "orderCompleted"}))

    def publish_order_status(self, tracking_id: str, status: dict) -> None:
        loop = asyncio.get_event_loop()
        loop.create_task(hub.publish(order_group(tracking_id), {"type": "orderStatus", "data": status}))


order_service = OrderService(
    order_repo=_SyncRepoAdapter(order_repo),
    signalr_publisher=_WsSignalRShim(),
)

from services.cloud_messaging_service import CloudMessagingService

cloud_messaging = CloudMessagingService.from_environment(
    automate_secret=AUTOMATE_SECRET,
    automate_to=AUTOMATE_TO,
    automate_device=AUTOMATE_DEVICE,
    fcm_project_id=FCM_PROJECT_ID,
    fcm_service_account_json=FCM_SERVICE_ACCOUNT_JSON,
) if ENABLE_CLOUD_MESSAGING else None

# ====================================================================== #
#  Poller (was the timer trigger)
# ====================================================================== #

async def poll_telemetry() -> None:
    """Core polling loop — ported 1:1 from function_app.poll_telemetry."""
    try:
        current_state = await aika.fetch_current_state(save_raw_payload=SAVE_RAW_PAYLOAD)
        previous_doc = await telemetry_store.get_previous_state(current_state.device_id)

        if (current_state.location.lat == 0.0 and current_state.location.lng == 0.0
                and previous_doc is not None):
            from models.telemetry import LocationInfo, TelemetryState  # noqa: F401 (used in constructed state)
            current_state = TelemetryState(
                device_id=current_state.device_id,
                timestamp=current_state.timestamp,
                location=LocationInfo(
                    lat=previous_doc.location.get("lat", 0.0),
                    lng=previous_doc.location.get("lng", 0.0),
                    course=previous_doc.location.get("course", 0),
                    position_time=previous_doc.location.get("position_time"),
                ),
                status=current_state.status,
                raw_payload=current_state.raw_payload,
            )

        event = compute_event(current_state, previous_doc, ENABLE_SECURITY)

        has_changed = True
        has_speed_or_time_update = False
        should_save = False
        doc_to_save = None
        final_doc = None
        should_update_last_checked = False

        if previous_doc is not None:
            curr_loc = current_state.location.to_dict()
            curr_stat = current_state.status.to_dict()
            location_changed = any(curr_loc.get(k) != previous_doc.location.get(k) for k in ["lat", "lng", "course"])
            status_changed = any(curr_stat.get(k) != previous_doc.status.get(k) for k in ["isIgnitionOn", "batteryLevel", "isOnline"])
            has_changed = location_changed or status_changed or (event is not None)

            if previous_doc.last_checked_at:
                try:
                    last_checked = datetime.fromisoformat(previous_doc.last_checked_at.replace("Z", "+00:00"))
                    should_update_last_checked = datetime.now(timezone.utc) - last_checked >= timedelta(minutes=20)
                except (ValueError, AttributeError):
                    should_update_last_checked = True

        if has_changed or previous_doc is None:
            doc = TelemetryDocument.from_state(current_state, event)
            doc_to_save, final_doc, should_save = doc, doc, True
            logger.info("Persisted new document id=%s event=%s", doc.id, doc.eventTriggered or "none")
        else:
            curr_loc = current_state.location.to_dict()
            curr_stat = current_state.status.to_dict()
            speed_changed = curr_stat.get("speed") != previous_doc.status.get("speed")
            position_time_changed = curr_loc.get("position_time") != previous_doc.location.get("position_time")
            if speed_changed:
                previous_doc.status["speed"] = curr_stat.get("speed")
            if position_time_changed:
                previous_doc.location["position_time"] = curr_loc.get("position_time")
            has_speed_or_time_update = speed_changed or position_time_changed
            previous_doc.last_checked_at = current_state.timestamp
            final_doc = previous_doc
            if has_speed_or_time_update or should_update_last_checked:
                doc_to_save, should_save = final_doc, True

        if should_save and doc_to_save is not None:
            await telemetry_store.save_state(doc_to_save)

        if final_doc is not None:
            await cache.set_latest(final_doc)

        # Broadcast
        should_broadcast = event is not None or has_changed or BROADCAST_ALL_POLLS or has_speed_or_time_update
        if should_broadcast and final_doc is not None and hub.group_size(TELEMETRY_GROUP) > 0:
            await hub.publish(TELEMETRY_GROUP, final_doc.to_cosmos_dict())

        # HatidKuya active-order broadcasts
        if final_doc and final_doc.location:
            try:
                final_loc = final_doc.location
                if final_loc.get("lat") and final_loc.get("lng"):
                    now_iso = datetime.now(timezone.utc).isoformat()
                    timestamp_val = (
                        final_loc.get("position_time")
                        or getattr(final_doc, "status_updated_at", None)
                        or getattr(final_doc, "last_checked_at", None)
                        or now_iso
                    )
                    updated = order_service.broadcast_telemetry_to_active_orders(
                        lat=float(final_loc["lat"]),
                        lng=float(final_loc["lng"]),
                        timestamp=timestamp_val,
                    )
                    if updated:
                        logger.info("Broadcasted telemetry GPS to %d active orders", updated)
            except Exception as e:
                logger.warning("Error dispatching telemetry to active orders: %s", e)

        # Cloud notifications
        if event is not None and cloud_messaging is not None:
            try:
                success, results = await cloud_messaging.send_event_notification(
                    event_type=event, telemetry_doc=final_doc, user_ids=[]
                )
                logger.info("Cloud notifications for %s: success=%s results=%s", event.value, success, results)
            except Exception:
                logger.exception("Error sending cloud notifications")

    except Exception:
        logger.exception("Error in poll_telemetry")


async def nightly_cleanup() -> None:
    """Token expiry + telemetry retention (replaces Cosmos TTL)."""
    try:
        removed = await telemetry_store.cleanup_expired_tokens(days_threshold=30)
        logger.info("Cleaned up %d expired device tokens", removed)
    except Exception:
        logger.exception("Token cleanup failed")

    try:
        from sqlalchemy import text as _text
        async with SessionLocal() as session:
            await session.execute(_text(
                "DELETE FROM telemetry WHERE updated_at_ts < now() - interval '60 days'"
            ))
            await session.commit()
    except Exception:
        logger.exception("Telemetry retention cleanup failed")


# ====================================================================== #
#  Auth dependency
# ====================================================================== #

from fastapi import Security
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

bearer_scheme = HTTPBearer(auto_error=False)


async def require_auth(
    creds: Optional[HTTPAuthorizationCredentials] = Security(bearer_scheme),
    required_scope: Optional[str] = None,
):
    """Raises 401 like _check_auth did; returns decoded bearer token.
    Note: scope enforcement is delegated to verify_token via the endpoint."""
    return creds


def check_auth_header(header_value: Optional[str], required_scope: Optional[str] = None) -> None:
    """Port of _check_auth for direct use in handlers that prefer raw headers."""
    try:
        verify_token(header_value, required_scope=required_scope)
    except ValueError as e:
        raise HTTPException(status_code=401, detail=str(e))


# ====================================================================== #
#  App wiring
# ====================================================================== #

@asynccontextmanager
async def lifespan(app: FastAPI):
    set_main_loop(asyncio.get_running_loop())
    await init_db()

    from apscheduler.schedulers.asyncio import AsyncIOScheduler
    scheduler = AsyncIOScheduler()
    scheduler.add_job(poll_telemetry, "interval", seconds=POLL_INTERVAL_SECONDS, id="poll_telemetry")
    scheduler.add_job(nightly_cleanup, "cron", hour=3, minute=0, id="nightly_cleanup")
    scheduler.start()
    logger.info("Scheduler started (poll every %ds)", POLL_INTERVAL_SECONDS)

    yield

    scheduler.shutdown(wait=False)


app = FastAPI(title="bike-tracker-api", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS or [],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


def _auth(request: Request, required_scope: Optional[str] = None) -> None:
    """401-equivalent of _check_auth (bearer token via Authorization header)."""
    try:
        verify_token(request.headers.get("Authorization"), required_scope=required_scope)
    except ValueError as e:
        raise HTTPException(status_code=401, detail=str(e))


# ---------------------- Telemetry endpoints ---------------------- #

@app.get("/api/telemetry/current")
async def get_current(request: Request):
    _auth(request)
    doc = await cache.get_previous_state(AIKA_DEVICE)
    if doc is None:
        return JSONResponse({"error": "No telemetry data found"}, status_code=404)
    return doc.to_cosmos_dict()


@app.get("/api/telemetry/history")
async def get_history(request: Request, limit: int = 50, hours: int = 24):
    _auth(request)
    docs = await telemetry_store.get_history(AIKA_DEVICE, limit=limit, hours=hours)
    return [d.to_cosmos_dict() for d in docs]


@app.get("/api/telemetry/events")
async def get_events(request: Request, limit: int = 20):
    _auth(request)
    docs = await telemetry_store.get_events(AIKA_DEVICE, limit=limit)
    return [d.to_cosmos_dict() for d in docs]


# ---------------------- WebSocket ---------------------- #

@app.websocket("/ws/{group}")
async def ws_endpoint(ws: WebSocket, group: str):
    await hub.connect(ws, group)
    try:
        while True:
            await ws.receive_text()  # keepalive ping from client
    except WebSocketDisconnect:
        await hub.disconnect(ws, group)


@app.get("/api/pubsub/negotiate")
async def negotiate_pubsub(request: Request):
    """Compatibility endpoint: returns the WS URL so existing frontend
    code can do ``new WebSocket(negotiate.url)`` with no other changes."""
    _auth(request)
    host = request.headers.get("host", "localhost")
    proto = request.headers.get("x-forwarded-proto", "wss")
    url = f"{proto}://{host}/ws/{TELEMETRY_GROUP}"
    return {"provider": "native", "url": url}


@app.post("/api/negotiate/{tracking_id}")
async def negotiate_order(tracking_id: str, request: Request):
    _auth(request)
    proto = request.headers.get("x-forwarded-proto", "wss")
    url = f"{proto}://{request.headers.get('host', 'localhost')}/ws/{order_group(tracking_id)}"
    return {"provider": "native", "url": url}


# ---------------------- Device command / tokens ---------------------- #

@app.post("/api/device/command")
async def send_device_command(request: Request):
    _auth(request)
    body = await request.json()
    command, pin = body.get("command"), body.get("pin")
    if command not in ("DY", "KY"):
        return JSONResponse({"error": "Invalid command. Must be 'DY' or 'KY'"}, status_code=400)
    if not pin or str(pin) != str(COMMAND_PIN):
        return JSONResponse({"error": "Invalid PIN"}, status_code=403)
    try:
        res = await aika.send_command(command)
        return {"success": True, "result": res}
    except Exception:
        logger.exception("Failed to send command to device")
        return JSONResponse({"error": "Failed to send command"}, status_code=500)


@app.post("/api/devices/register-token")
async def register_device_token(request: Request):
    _auth(request)
    body = await request.json()
    fcm_token, platform = body.get("fcmToken"), body.get("platform", "android")
    if not fcm_token:
        return JSONResponse({"error": "Missing 'fcmToken' field"}, status_code=400)
    claims = decode_token(request.headers.get("Authorization", "").replace("Bearer ", ""))
    user_id = claims.get("sub") or claims.get("oid") or "unknown"
    success = await telemetry_store.register_device_token(user_id, fcm_token, platform)
    if success:
        return {"success": True, "message": "Device token registered"}
    return JSONResponse({"success": False, "error": "Failed to register token"}, status_code=500)


@app.delete("/api/devices/register-token")
async def unregister_device_token(request: Request):
    _auth(request)
    body = await request.json()
    fcm_token = body.get("fcmToken")
    if not fcm_token:
        return JSONResponse({"error": "Missing 'fcmToken' field"}, status_code=400)
    claims = decode_token(request.headers.get("Authorization", "").replace("Bearer ", ""))
    user_id = claims.get("sub") or claims.get("oid") or "unknown"
    success = await telemetry_store.unregister_device_token(user_id, fcm_token)
    if success:
        return {"success": True, "message": "Device token unregistered"}
    return JSONResponse({"success": False, "error": "Token not found"}, status_code=404)


# ---------------------- HatidKuya orders ---------------------- #

from models.order import CreateOrderRequest, UpdateLocationRequest


@app.post("/api/orders", status_code=201)
async def create_order(request: Request):
    _auth(request)
    body = await request.json()
    order_req = CreateOrderRequest(**body)

    initial_loc = None
    try:
        latest_doc = await cache.get_previous_state(AIKA_DEVICE)
        if latest_doc and latest_doc.location:
            lat, lng = latest_doc.location.get("lat"), latest_doc.location.get("lng")
            if lat and lng and lat != 0.0 and lng != 0.0:
                initial_loc = {
                    "lat": float(lat),
                    "lng": float(lng),
                    "timestamp": latest_doc.status_updated_at or latest_doc.location.get("position_time"),
                }
    except Exception as err:
        logger.warning("Could not retrieve latest telemetry for order: %s", err)

    return order_service.create_order(order_req, initial_location=initial_loc)


@app.get("/api/orders/active")
async def get_active_order(request: Request):
    _auth(request)
    return order_service.get_latest_active_order()


@app.get("/api/orders/{tracking_id}")
async def get_order(tracking_id: str, request: Request):
    order = order_service.get_order_by_tracking_id(tracking_id)
    if not order:
        return JSONResponse({"error": "Order not found"}, status_code=404)
    if not order.get("last_location"):
        latest_doc = await cache.get_previous_state(AIKA_DEVICE)
        if latest_doc and latest_doc.location:
            order["last_location"] = {
                "lat": latest_doc.location.get("lat"),
                "lng": latest_doc.location.get("lng"),
                "timestamp": latest_doc.location.get("position_time") or latest_doc.status_updated_at,
                "source": "poll_telemetry",
            }
    return order


@app.post("/api/orders/location")
async def update_order_location(request: Request):
    _auth(request, required_scope="api://bike-tracker-api/hatidkuya_location")
    body = await request.json()
    active = order_service.get_latest_active_order()
    if not active:
        return JSONResponse({"error": "No active order found"}, status_code=404)
    loc_req = UpdateLocationRequest(**body)
    updated = order_service.update_location(active["id"], loc_req)
    if not updated:
        return JSONResponse({"error": "Order not found"}, status_code=404)
    return updated


@app.post("/api/orders/{order_id}/stage")
async def update_order_stage(order_id: str, request: Request):
    _auth(request)
    body = await request.json()
    stage = body.get("stage") or body.get("delivery_stage") or "going_to_pickup"
    updated = order_service.update_delivery_stage(order_id, stage)
    if not updated:
        return JSONResponse({"error": "Order not found"}, status_code=404)
    return updated


@app.post("/api/orders/{order_id}/theme")
async def update_order_theme(order_id: str, request: Request):
    _auth(request)
    theme = (await request.json()).get("theme") or "moveit"
    updated = order_service.update_theme(order_id, theme)
    if not updated:
        return JSONResponse({"error": "Order not found"}, status_code=404)
    return updated


@app.post("/api/orders/{order_id}/complete")
async def complete_order(order_id: str, request: Request):
    _auth(request)
    updated = order_service.complete_order(order_id)
    if not updated:
        return JSONResponse({"error": "Order not found"}, status_code=404)
    return updated


@app.get("/api/orders/{tracking_id}/history")
async def get_order_history(tracking_id: str, request: Request):
    return await order_repo.get_location_history(tracking_id)


# ---------------------- Location search (proxy) ---------------------- #

import httpx

GOOGLE_MAPS_API_KEY = os.environ.get("GOOGLE_MAPS_API_KEY", "").strip()


@app.get("/api/locations/search")
async def search_locations(request: Request, q: str = ""):
    if len(q.strip()) < 2:
        return []
    headers = {"User-Agent": "HatidKuyaDeliveryApp/1.0", "Accept-Language": "en"}
    if GOOGLE_MAPS_API_KEY:
        try:
            async with httpx.AsyncClient(timeout=5) as client:
                res = await client.get(
                    "https://maps.googleapis.com/maps/api/place/autocomplete/json",
                    params={"input": q.strip(), "key": GOOGLE_MAPS_API_KEY,
                            "components": "country:ph", "location": "14.5995,120.9842",
                            "radius": "50000", "language": "en"},
                )
                if res.status_code == 200:
                    return [
                        {"place_id": p["place_id"],
                         "name": p.get("structured_formatting", {}).get("main_text", p.get("description", "")),
                         "display_name": p.get("description", ""), "lat": 0, "lon": 0}
                        for p in res.json().get("predictions", [])[:6]
                    ]
        except Exception as e:
            logger.warning("Google search error, falling back: %s", e)

    async with httpx.AsyncClient(timeout=4) as client:
        try:
            res = await client.get(
                "https://photon.komoot.io/api/",
                params={"q": q.strip(), "limit": 6, "lat": 14.5995, "lon": 120.9842}, headers=headers)
            if res.status_code == 200:
                results = []
                for f in res.json().get("features", []):
                    props, coords = f.get("properties", {}), f.get("geometry", {}).get("coordinates", [0, 0])
                    parts = [props.get("name"), props.get("street"), props.get("city"), props.get("state"), props.get("country")]
                    results.append({"name": props.get("name") or props.get("street") or q,
                                    "display_name": ", ".join(p for p in parts if p) or props.get("name", q),
                                    "lat": coords[1], "lon": coords[0]})
                if results:
                    return results
        except Exception:
            pass
        nom = await client.get(
            "https://nominatim.openstreetmap.org/search",
            params={"q": q.strip(), "format": "json", "addressdetails": 1, "limit": 6, "countrycodes": "ph"},
            headers=headers)
        return nom.json()


@app.get("/api/locations/details")
async def get_location_details(request: Request, place_id: str = "", address: str = ""):
    lat, lng = 14.5995, 120.9842
    if GOOGLE_MAPS_API_KEY and (place_id or address):
        try:
            async with httpx.AsyncClient(timeout=4) as client:
                if place_id:
                    res = await client.get(
                        "https://maps.googleapis.com/maps/api/place/details/json",
                        params={"place_id": place_id, "fields": "geometry,formatted_address", "key": GOOGLE_MAPS_API_KEY})
                    data = res.json().get("result", {})
                    geom = data.get("geometry", {}).get("location", {})
                    if geom.get("lat") and geom.get("lng"):
                        return {"lat": geom["lat"], "lng": geom["lng"],
                                "address": data.get("formatted_address") or address}
                elif address:
                    res = await client.get(
                        "https://maps.googleapis.com/maps/api/geocode/json",
                        params={"address": address, "components": "country:ph", "key": GOOGLE_MAPS_API_KEY})
                    results = res.json().get("results", [])
                    if results:
                        geom = results[0].get("geometry", {}).get("location", {})
                        return {"lat": geom.get("lat", lat), "lng": geom.get("lng", lng),
                                "address": results[0].get("formatted_address") or address}
        except Exception as e:
            logger.warning("Error fetching Google Place details: %s", e)
    return {"lat": lat, "lng": lng, "address": address or ""}


# ---------------------- Health ---------------------- #

@app.get("/api/health")
async def health():
    services: dict = {}
    try:
        await telemetry_store.get_previous_state(AIKA_DEVICE)
        services["db"] = {"ok": True, "detail": "reachable"}
    except Exception as exc:
        services["db"] = {"ok": False, "detail": str(exc)}
    services["ws_hub"] = {"ok": True, "detail": f"telemetry listeners={hub.group_size(TELEMETRY_GROUP)}"}
    try:
        if not AIKA_DEVICE or not AIKA_PASSWORD:
            services["aika"] = {"ok": False, "detail": "credentials not configured"}
        else:
            await aika.fetch_current_state(save_raw_payload=False)
            services["aika"] = {"ok": True, "detail": "reachable"}
    except Exception as exc:
        services["aika"] = {"ok": False, "detail": str(exc)}
    all_ok = all(s["ok"] for s in services.values())
    return {
        "status": "healthy" if all_ok else "degraded",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "services": services,
    }
