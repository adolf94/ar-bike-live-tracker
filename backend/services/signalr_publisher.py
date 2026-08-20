import os
import time
import jwt
import requests
from typing import Dict, Any, Optional
import logging

logger = logging.getLogger(__name__)


class SignalRPublisher:
    def __init__(self):
        self.conn_str = os.environ.get("AZURE_SIGNALR_CONNECTION_STRING", "")
        self.endpoint, self.access_key = self._parse_connection_string(self.conn_str)
        self.hub_name = "trackingHub"

    def _parse_connection_string(self, conn_str: str):
        endpoint = "http://localhost:8888"
        access_key = "ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789ABCDEFGH"
        if not conn_str:
            return endpoint, access_key
        parts = dict(item.split("=", 1) for item in conn_str.split(";") if "=" in item)
        endpoint = parts.get("Endpoint", endpoint).rstrip("/")
        port = parts.get("Port")
        if port and not (endpoint.endswith(f":{port}") or ":" in endpoint.split("//")[-1]):
            endpoint = f"{endpoint}:{port}"
        access_key = parts.get("AccessKey", access_key)
        return endpoint, access_key

    def generate_token(self, url: str, user_id: Optional[str] = None, group: Optional[str] = None, ttl_seconds: int = 3600) -> str:
        now = int(time.time())
        payload = {
            "aud": url,
            "exp": now + ttl_seconds,
            "iat": now,
            "nbf": now,
        }
        if user_id:
            payload["sub"] = user_id
        if group:
            payload["asrs.s.gid"] = group

        return jwt.encode(payload, self.access_key, algorithm="HS256")

    def negotiate(self, tracking_id: str) -> Dict[str, str]:
        group_name = f"order-{tracking_id}"
        hub_url = f"{self.endpoint}/client/hubs/{self.hub_name}"
        token = self.generate_token(hub_url, group=group_name)
        return {
            "url": hub_url,
            "accessToken": token
        }

    def check_group_has_users(self, group_name: str) -> bool:
        """Check if group currently has active connections/users in Azure SignalR / WebPubSub."""
        # Azure SignalR REST API: GET /api/v1/hubs/{hub}/groups/{group}/connections/:check or HEAD /api/v1/hubs/{hub}/groups/{group}
        url = f"{self.endpoint}/api/v1/hubs/{self.hub_name}/groups/{group_name}"
        token = self.generate_token(url)
        headers = {
            "Authorization": f"Bearer {token}"
        }
        try:
            resp = requests.head(url, headers=headers, timeout=3)
            # 200 means group exists and has members; 404 means no active connections
            if resp.status_code == 200:
                return True
            if resp.status_code == 404:
                return False
            # For emulator or fallback servers that return 200/400, assume True
            return True
        except Exception:
            # Fallback to True if check endpoint is unsupported
            return True

    def broadcast_to_group(self, group_name: str, target: str, arguments: list, only_if_connected: bool = True) -> bool:
        if only_if_connected and not self.check_group_has_users(group_name):
            logger.debug("Skipping broadcast to group %s — no active subscribers", group_name)
            return False

        url = f"{self.endpoint}/api/v1/hubs/{self.hub_name}/groups/{group_name}/:send"
        token = self.generate_token(url)
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {token}"
        }
        body = {
            "target": target,
            "arguments": arguments
        }
        try:
            resp = requests.post(url, json=body, headers=headers, timeout=5)
            if resp.status_code not in (200, 202):
                logger.warning("SignalR broadcast returned status %d: %s", resp.status_code, resp.text)
                return False
            return True
        except Exception as e:
            logger.warning("SignalR broadcast failed (will not break request): %s", e)
            return False

    def publish_location(self, tracking_id: str, location_data: Dict[str, Any], only_if_connected: bool = True) -> bool:
        group_name = f"order-{tracking_id}"
        return self.broadcast_to_group(group_name, "locationUpdate", [location_data], only_if_connected=only_if_connected)

    def publish_order_completed(self, tracking_id: str) -> bool:
        group_name = f"order-{tracking_id}"
        return self.broadcast_to_group(group_name, "orderCompleted", [], only_if_connected=False)

