import os
import time
import jwt
import requests
from typing import Dict, Any, Optional
import logging

logger = logging.getLogger(__name__)


class SignalRPublisher:
    def __init__(self):
        self.conn_str = os.environ.get("AZURE_SIGNALR_CONNECTION_STRING", "") or os.environ.get("WebPubSubConnectionString", "")
        self.endpoint, self.access_key = self._parse_connection_string(self.conn_str)
        self.hub_name = os.environ.get("WEBPUBSUB_HUB_NAME", "tracking_hub")

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
        hub_url = f"{self.endpoint}/client/?hub={self.hub_name}"
        token = self.generate_token(hub_url, group=group_name)
        return {
            "url": hub_url,
            "accessToken": token
        }

    def add_connection_to_group(self, connection_id: str, group_name: str) -> bool:
        """Add a connection to a group via Azure SignalR REST API (serverless mode)."""
        url = f"{self.endpoint}/api/v1/hubs/{self.hub_name}/groups/{group_name}/connections/{connection_id}"
        token = self.generate_token(url)
        headers = {"Authorization": f"Bearer {token}"}
        try:
            resp = requests.put(url, headers=headers, timeout=5)
            if resp.status_code in (200, 202, 204):
                logger.info("Added connection %s to group %s", connection_id, group_name)
                return True
            logger.warning("add_connection_to_group returned %d: %s", resp.status_code, resp.text)
            return False
        except Exception as e:
            logger.warning("add_connection_to_group failed: %s", e)
            return False

    def check_group_has_users(self, group_name: str) -> bool:
        """Check if group currently has active connections/users in Azure SignalR / WebPubSub."""
        url = f"{self.endpoint}/api/v1/hubs/{self.hub_name}/groups/{group_name}"
        token = self.generate_token(url)
        headers = {"Authorization": f"Bearer {token}"}
        try:
            resp = requests.head(url, headers=headers, timeout=3)
            # 200 means group exists and has members; 404 means no active connections
            if resp.status_code == 200:
                return True
            if resp.status_code == 404:
                return False
            return True
        except Exception:
            return True

    def broadcast_to_group(self, group_name: str, target: str, arguments: list, only_if_connected: bool = False) -> bool:
        if only_if_connected and not self.check_group_has_users(group_name):
            logger.debug("Skipping broadcast to group %s — no active subscribers", group_name)
            return False

        # Azure SignalR Service REST API group broadcast endpoint
        url = f"{self.endpoint}/api/v1/hubs/{self.hub_name}/groups/{group_name}"
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
            # 404 on /groups/{group_name} can happen if group does not exist yet; try /groups/{group_name}/:send or hub fallback
            if resp.status_code == 404:
                send_url = f"{self.endpoint}/api/v1/hubs/{self.hub_name}/groups/{group_name}/:send"
                send_token = self.generate_token(send_url)
                resp = requests.post(send_url, json=body, headers={"Content-Type": "application/json", "Authorization": f"Bearer {send_token}"}, timeout=5)
            if resp.status_code not in (200, 202):
                logger.warning("SignalR broadcast returned status %d: %s", resp.status_code, resp.text)
                return False
            return True
        except Exception as e:
            logger.warning("SignalR broadcast failed (will not break request): %s", e)
            return False

    def publish_location(self, tracking_id: str, location_data: Dict[str, Any], only_if_connected: bool = False) -> bool:
        group_name = f"order-{tracking_id}"
        logger.info("publish_location → group=%s lat=%s lng=%s only_if_connected=%s",
                    group_name, location_data.get("lat"), location_data.get("lng"), only_if_connected)
        res = self.broadcast_to_group(group_name, "locationUpdate", [location_data], only_if_connected=only_if_connected)

        # Also broadcast to hub level with trackingId so all connected clients receive the update
        url = f"{self.endpoint}/api/v1/hubs/{self.hub_name}"
        token = self.generate_token(url)
        headers = {"Content-Type": "application/json", "Authorization": f"Bearer {token}"}
        body = {"target": "locationUpdate", "arguments": [{**location_data, "trackingId": tracking_id}]}
        try:
            requests.post(url, json=body, headers=headers, timeout=5)
        except Exception as e:
            logger.warning("Hub-level location broadcast failed: %s", e)

        return res

    def publish_order_status(self, tracking_id: str, status_data: Dict[str, Any]) -> bool:
        group_name = f"order-{tracking_id}"
        logger.info("Publishing statusUpdate to group %s: %s", group_name, status_data)
        self.broadcast_to_group(group_name, "statusUpdate", [status_data], only_if_connected=False)
        # Also broadcast to hub level with trackingId payload for global listeners
        url = f"{self.endpoint}/api/v1/hubs/{self.hub_name}"
        token = self.generate_token(url)
        headers = {"Content-Type": "application/json", "Authorization": f"Bearer {token}"}
        body = {"target": "statusUpdate", "arguments": [{**status_data, "trackingId": tracking_id}]}
        try:
            requests.post(url, json=body, headers=headers, timeout=5)
        except Exception as e:
            logger.warning("Hub-level status broadcast failed: %s", e)
        return True

    def publish_order_completed(self, tracking_id: str) -> bool:
        group_name = f"order-{tracking_id}"
        self.broadcast_to_group(group_name, "orderCompleted", [], only_if_connected=False)
        # Also broadcast to hub level
        url = f"{self.endpoint}/api/v1/hubs/{self.hub_name}"
        token = self.generate_token(url)
        headers = {"Content-Type": "application/json", "Authorization": f"Bearer {token}"}
        body = {"target": "orderCompleted", "arguments": [{"trackingId": tracking_id}]}
        try:
            requests.post(url, json=body, headers=headers, timeout=5)
        except Exception as e:
            logger.warning("Hub-level orderCompleted broadcast failed: %s", e)
        return True

