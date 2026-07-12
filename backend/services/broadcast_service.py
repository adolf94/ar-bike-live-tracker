import json
import logging
import time
import httpx
import jwt
from typing import Any, Dict

logger = logging.getLogger(__name__)


class BroadcastService:
    """Dynamically manages broadcasting event payloads to connected clients.
    
    Supports both Azure Web PubSub and Azure SignalR Service (or emulator).
    Automatically detects the provider type from the connection string endpoint.
    """

    def __init__(self, connection_string: str, hub_name: str = "telemetry_hub"):
        self._hub_name = hub_name
        self._connection_string = connection_string
        self._client = None
        self.provider = "webpubsub"

        if not connection_string:
            logger.warning("No connection string provided for BroadcastService")
            return

        # Parse connection string
        self._conn_dict = self._parse_connection_string(connection_string)
        endpoint = self._conn_dict.get("Endpoint", "").rstrip("/")
        port = self._conn_dict.get("Port", "")
        self._access_key = self._conn_dict.get("AccessKey", "")
        self._base_url = f"{endpoint}:{port}" if port else endpoint

        # Auto-detect provider
        if "localhost" in endpoint or "127.0.0.1" in endpoint or "service.signalr" in endpoint or (port and "8888" in port):
            self.provider = "signalr"
            logger.info("Auto-detected SignalR provider for BroadcastService (Endpoint: %s)", self._base_url)
        else:
            self.provider = "webpubsub"
            logger.info("Auto-detected Web PubSub provider for BroadcastService (Endpoint: %s)", self._base_url)
            from azure.messaging.webpubsubservice import WebPubSubServiceClient
            self._client = WebPubSubServiceClient.from_connection_string(
                connection_string=connection_string,
                hub=hub_name,
            )

    def _parse_connection_string(self, conn_str: str) -> Dict[str, str]:
        result = {}
        for pair in conn_str.split(";"):
            if "=" in pair:
                key, val = pair.split("=", 1)
                result[key.strip()] = val.strip()
        return result

    async def broadcast_event(self, payload: Dict[str, Any]) -> None:
        """Send a JSON payload to all connected clients."""
        if self.provider == "webpubsub":
            if not self._client:
                logger.error("Web PubSub client not initialized")
                return
            try:
                message = json.dumps(payload)
                self._client.send_to_all(
                    message=message,
                    content_type="application/json",
                )
                logger.info(
                    "Broadcasted event '%s' via Web PubSub",
                    payload.get("eventTriggered", "unknown"),
                )
            except Exception:
                logger.exception("Failed to broadcast event to Web PubSub")
        else:
            # SignalR REST API broadcast
            url = f"{self._base_url}/api/v1/hubs/{self._hub_name}"
            token = self._generate_token(url)
            headers = {
                "Content-Type": "application/json",
                "Authorization": f"Bearer {token}",
            }
            body = {
                "target": "SendMessage",
                "arguments": [payload],
            }
            try:
                async with httpx.AsyncClient() as http_client:
                    res = await http_client.post(url, json=body, headers=headers)
                    if res.status_code >= 300:
                        logger.error(
                            "SignalR broadcast failed with status %d: %s",
                            res.status_code,
                            res.text,
                        )
                    else:
                        logger.info(
                            "Broadcasted event '%s' via SignalR",
                            payload.get("eventTriggered", "unknown"),
                        )
            except Exception:
                logger.exception("Failed to broadcast event to SignalR")

    def _generate_token(self, audience: str) -> str:
        """Generate a signed JWT token using HS256 algorithm with AccessKey."""
        payload = {
            "aud": audience,
            "exp": int(time.time()) + 3600,
            "sub": "anonymous",
        }
        return jwt.encode(payload, self._access_key, algorithm="HS256")

    def get_client_access_url(self, user_id: str = "anonymous", request_hostname: str = None) -> str:
        """Generate a client access URL with a short-lived token."""
        if self.provider == "webpubsub":
            if not self._client:
                raise ValueError("Web PubSub client not initialized")
            try:
                token = self._client.get_client_access_token(
                    user_id=user_id,
                    roles=["webpubsub.joinLeaveGroup", "webpubsub.sendToGroup"],
                )
                return token["url"]
            except Exception:
                logger.exception("Failed to generate client access URL for Web PubSub")
                raise
        else:
            # SignalR Client Handshake URL
            base_url = self._base_url
            if request_hostname:
                base_url = base_url.replace("localhost", request_hostname).replace("127.0.0.1", request_hostname)
            client_url = f"{base_url}/client/?hub={self._hub_name}"
            token = self._generate_token(client_url)
            return f"{client_url}&access_token={token}"
