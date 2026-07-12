"""Azure Web PubSub broadcaster service."""

import json
import logging
from typing import Any, Dict

from azure.messaging.webpubsubservice import WebPubSubServiceClient

logger = logging.getLogger(__name__)


class PubSubService:
    """Manages broadcasting event payloads to Web PubSub connected clients.

    Uses the ``azure-messaging-webpubsubservice`` SDK to send messages
    to the ``telemetry_hub`` hub.
    """

    def __init__(self, connection_string: str, hub_name: str = "telemetry_hub"):
        self._hub_name = hub_name
        self._client = WebPubSubServiceClient.from_connection_string(
            connection_string=connection_string,
            hub=hub_name,
        )

    async def broadcast_event(self, payload: Dict[str, Any]) -> None:
        """Send a JSON payload to all connected clients in the hub."""
        try:
            message = json.dumps(payload)
            self._client.send_to_all(
                message=message,
                content_type="application/json",
            )
            logger.info(
                "Broadcasted event '%s' to hub '%s'",
                payload.get("eventTriggered", "unknown"),
                self._hub_name,
            )
        except Exception:
            logger.exception("Failed to broadcast event to Web PubSub")

    def get_client_access_url(self, user_id: str = "anonymous") -> str:
        """Generate a client access URL with a short-lived token.

        Frontend clients call this via the ``/api/pubsub/negotiate``
        HTTP endpoint to obtain a WebSocket URL they can connect to.
        """
        try:
            token = self._client.get_client_access_token(
                user_id=user_id,
                roles=["webpubsub.joinLeaveGroup", "webpubsub.sendToGroup"],
            )
            return token["url"]
        except Exception:
            logger.exception("Failed to generate client access URL")
            raise
