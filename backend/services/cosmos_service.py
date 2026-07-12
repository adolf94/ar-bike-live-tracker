"""Cosmos DB read operations via the azure-cosmos SDK."""

import logging
from datetime import datetime, timezone, timedelta
from typing import List, Optional

from azure.cosmos import CosmosClient
from azure.cosmos.exceptions import CosmosResourceNotFoundError

from models.documents import TelemetryDocument

logger = logging.getLogger(__name__)


class CosmosService:
    """Encapsulates all Cosmos DB read queries.

    Write operations are handled by the Azure Functions Cosmos DB output
    binding (declarative), so this service only covers reads.
    """

    def __init__(
        self,
        connection_string: str,
        database_name: str,
        container_name: str,
    ):
        self._client = CosmosClient.from_connection_string(connection_string)
        self._database = self._client.get_database_client(database_name)
        self._container = self._database.get_container_client(container_name)

    # ------------------------------------------------------------------ #
    #  Previous state (used by the poller for event computation)
    # ------------------------------------------------------------------ #

    async def get_previous_state(
        self, device_id: str
    ) -> Optional[TelemetryDocument]:
        """Return the single most-recent telemetry document for *device_id*.

        Query::

            SELECT TOP 1 *
            FROM c
            WHERE c.deviceId = @deviceId
            ORDER BY c.status_updated_at DESC
        """
        query = (
            "SELECT TOP 1 * FROM c "
            "WHERE c.deviceId = @deviceId "
            "ORDER BY c.status_updated_at DESC"
        )
        parameters = [{"name": "@deviceId", "value": device_id}]

        try:
            items = list(
                self._container.query_items(
                    query=query,
                    parameters=parameters,
                    partition_key=device_id,
                )
            )
            if items:
                return TelemetryDocument.from_cosmos_dict(items[0])
        except CosmosResourceNotFoundError:
            logger.warning(
                "Container not found — returning None for previous state."
            )
        except Exception:
            logger.exception("Error querying previous state for %s", device_id)

        return None

    # ------------------------------------------------------------------ #
    #  History (used by HTTP endpoint)
    # ------------------------------------------------------------------ #

    async def get_history(
        self, device_id: str, limit: int = 50, hours: int = 24
    ) -> List[TelemetryDocument]:
        """Return recent telemetry records within the given time window."""
        since = (
            datetime.now(timezone.utc) - timedelta(hours=hours)
        ).isoformat()

        query = (
            "SELECT TOP @limit * FROM c "
            "WHERE c.deviceId = @deviceId AND c.status_updated_at >= @since "
            "ORDER BY c.status_updated_at DESC"
        )
        parameters = [
            {"name": "@deviceId", "value": device_id},
            {"name": "@limit", "value": limit},
            {"name": "@since", "value": since},
        ]

        try:
            items = list(
                self._container.query_items(
                    query=query,
                    parameters=parameters,
                    partition_key=device_id,
                )
            )
            return [TelemetryDocument.from_cosmos_dict(i) for i in items]
        except Exception:
            logger.exception("Error querying history for %s", device_id)
            return []

    # ------------------------------------------------------------------ #
    #  Events only (used by HTTP endpoint)
    # ------------------------------------------------------------------ #

    async def get_events(
        self, device_id: str, limit: int = 20
    ) -> List[TelemetryDocument]:
        """Return recent documents where ``eventTriggered`` is not null."""
        query = (
            "SELECT TOP @limit * FROM c "
            "WHERE c.deviceId = @deviceId "
            "AND IS_DEFINED(c.eventTriggered) "
            "AND c.eventTriggered != null "
            "ORDER BY c.status_updated_at DESC"
        )
        parameters = [
            {"name": "@deviceId", "value": device_id},
            {"name": "@limit", "value": limit},
        ]

        try:
            items = list(
                self._container.query_items(
                    query=query,
                    parameters=parameters,
                    partition_key=device_id,
                )
            )
            return [TelemetryDocument.from_cosmos_dict(i) for i in items]
        except Exception:
            logger.exception("Error querying events for %s", device_id)
            return []
