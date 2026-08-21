import os
from typing import Dict, Any, Optional
from datetime import datetime, timezone
from models.order import Order, CreateOrderRequest, UpdateLocationRequest
from repositories.order_repository import OrderRepository
from .signalr_publisher import SignalRPublisher


class OrderService:
    def __init__(self, order_repo: Optional[OrderRepository] = None, signalr_publisher: Optional[SignalRPublisher] = None):
        self.order_repo = order_repo or OrderRepository()
        self.signalr_publisher = signalr_publisher or SignalRPublisher()
        self.frontend_url = os.environ.get("FRONTEND_URL", "http://localhost:5173").rstrip("/")
        self._cached_active_order: Optional[Dict[str, Any]] = None
        self._last_telemetry_broadcast: Dict[str, datetime] = {}

    def create_order(self, req: CreateOrderRequest, initial_location: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        from models.order import Location
        initial_loc_model = None
        if initial_location and initial_location.get("lat") and initial_location.get("lng"):
            initial_loc_model = Location(
                lat=float(initial_location["lat"]),
                lng=float(initial_location["lng"]),
                timestamp=initial_location.get("timestamp") or datetime.now(timezone.utc).isoformat()
            )

        from_coords_model = None
        if req.from_lat is not None and req.from_lng is not None:
            from_coords_model = Location(lat=req.from_lat, lng=req.from_lng)

        to_coords_model = None
        if req.to_lat is not None and req.to_lng is not None:
            to_coords_model = Location(lat=req.to_lat, lng=req.to_lng)

        order = Order(
            from_address=req.from_address,
            to_address=req.to_address,
            from_coords=from_coords_model,
            to_coords=to_coords_model,
            recipient_name=req.recipient_name,
            item_description=req.item_description,
            status="active",
            last_location=initial_loc_model
        )
        saved = self.order_repo.create(order)
        self._cached_active_order = saved
        tracking_id = saved["tracking_id"]

        # Seed initial location history point
        if initial_loc_model:
            self.order_repo.add_location_history(
                order_id=saved["id"],
                tracking_id=tracking_id,
                lat=initial_loc_model.lat,
                lng=initial_loc_model.lng,
                timestamp=initial_loc_model.timestamp
            )

        return {
            "orderId": saved["id"],
            "trackingId": tracking_id,
            "trackingUrl": f"{self.frontend_url}/track/{tracking_id}",
            "fromAddress": saved["from_address"],
            "toAddress": saved["to_address"],
            "fromCoords": from_coords_model.model_dump() if from_coords_model else None,
            "toCoords": to_coords_model.model_dump() if to_coords_model else None,
            "recipientName": saved.get("recipient_name"),
            "itemDescription": saved.get("item_description"),
            "status": saved["status"],
            "lastLocation": initial_loc_model.model_dump() if initial_loc_model else None,
            "createdAt": saved["created_at"]
        }

    def get_order_by_tracking_id(self, tracking_id: str) -> Optional[Dict[str, Any]]:
        if self._cached_active_order and self._cached_active_order.get("tracking_id") == tracking_id:
            return self._cached_active_order
        return self.order_repo.get_by_tracking_id(tracking_id)

    def get_latest_active_order(self) -> Optional[Dict[str, Any]]:
        if self._cached_active_order and self._cached_active_order.get("status") == "active":
            return self._cached_active_order
        order = self.order_repo.get_latest_active_order()
        self._cached_active_order = order
        return order

    def broadcast_telemetry_to_active_orders(self, lat: float, lng: float, timestamp: Optional[str] = None) -> int:
        """Broadcast live polled telemetry location to active delivery orders unless manual GPS stream is active."""
        if lat == 0.0 and lng == 0.0:
            return 0

        active_orders = self.order_repo.get_active_orders()
        if not active_orders:
            return 0

        now_utc = datetime.now(timezone.utc)
        loc_data = {
            "lat": lat,
            "lng": lng,
            "timestamp": timestamp or now_utc.isoformat(),
            "source": "poll_telemetry"
        }

        updated_count = 0
        for order in active_orders:
            try:
                order_id = order.get("id")
                # Debounce telemetry broadcast to 55 seconds per order
                if order_id in self._last_telemetry_broadcast:
                    last_broadcast = self._last_telemetry_broadcast[order_id]
                    if (now_utc - last_broadcast).total_seconds() < 55:
                        continue

                # If order is receiving active manual GPS stream within the last 125 seconds, prioritize it!
                last_loc = order.get("last_location")
                if last_loc and last_loc.get("source") == "manual_gps":
                    last_ts_str = last_loc.get("timestamp")
                    if last_ts_str:
                        try:
                            last_ts = datetime.fromisoformat(last_ts_str.replace("Z", "+00:00"))
                            if (now_utc - last_ts).total_seconds() < 125:
                                # Skip overwriting active manual GPS broadcast
                                continue
                        except Exception:
                            pass

                # Persist latest polled location to CosmosDB
                order["last_location"] = loc_data
                self.order_repo.update(order)

                tracking_id = order.get("tracking_id")
                if tracking_id:
                    # Save path history point in OrderLocationHistory container
                    self.order_repo.add_location_history(
                        order_id=order_id,
                        tracking_id=tracking_id,
                        lat=lat,
                        lng=lng,
                        timestamp=loc_data["timestamp"]
                    )
                    # Publish via SignalR only if subscribers are connected to order group
                    self.signalr_publisher.publish_location(tracking_id, loc_data, only_if_connected=True)

                if order_id:
                    self._last_telemetry_broadcast[order_id] = now_utc

                updated_count += 1
            except Exception as e:
                import logging
                logging.getLogger(__name__).warning("Error updating/broadcasting telemetry to order %s: %s", order.get("id"), e)

        return updated_count

    def update_location(self, order_id: str, req: UpdateLocationRequest) -> Optional[Dict[str, Any]]:
        order = self.order_repo.get_by_id(order_id)
        if not order:
            return None

        loc_data = {
            "lat": req.lat,
            "lng": req.lng,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "source": "manual_gps"
        }
        order["last_location"] = loc_data
        updated = self.order_repo.update(order)

        if self._cached_active_order and self._cached_active_order.get("id") == order_id:
            self._cached_active_order["last_location"] = loc_data

        tracking_id = order.get("tracking_id")
        if tracking_id:
            # Save location history point
            self.order_repo.add_location_history(
                order_id=order.get("id"),
                tracking_id=tracking_id,
                lat=req.lat,
                lng=req.lng,
                timestamp=loc_data["timestamp"]
            )
            # Broadcast event to SignalR group
            self.signalr_publisher.publish_location(tracking_id, loc_data)

        return updated

    def get_order_history(self, tracking_id: str) -> list[Dict[str, Any]]:
        return self.order_repo.get_location_history(tracking_id)

    def update_delivery_stage(self, order_id: str, delivery_stage: str) -> Optional[Dict[str, Any]]:
        order = self.order_repo.get_by_id(order_id)
        if not order:
            return None

        order["delivery_stage"] = delivery_stage
        if delivery_stage == "completed":
            order["status"] = "completed"

        updated = self.order_repo.update(order)

        if delivery_stage == "completed":
            if self._cached_active_order and self._cached_active_order.get("id") == order_id:
                self._cached_active_order = None
        elif self._cached_active_order and self._cached_active_order.get("id") == order_id:
            self._cached_active_order["delivery_stage"] = delivery_stage

        tracking_id = order.get("tracking_id")
        if tracking_id:
            if delivery_stage == "completed":
                self.signalr_publisher.publish_order_completed(tracking_id)
            else:
                self.signalr_publisher.publish_order_status(tracking_id, {
                    "deliveryStage": delivery_stage,
                    "status": order.get("status", "active")
                })

        return updated

    def complete_order(self, order_id: str) -> Optional[Dict[str, Any]]:
        return self.update_delivery_stage(order_id, "completed")
