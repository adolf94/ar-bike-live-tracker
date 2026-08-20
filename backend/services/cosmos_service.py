"""Cosmos DB read operations via the azure-cosmos SDK."""

import logging
from datetime import datetime, timezone, timedelta
from typing import List, Optional

from azure.cosmos import CosmosClient
from azure.cosmos.exceptions import CosmosResourceNotFoundError
from azure.identity import DefaultAzureCredential

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
        endpoint: str = None,
    ):
        conn_str = (connection_string or "").strip()
        end_pt = (endpoint or "").strip()

        if conn_str:
            self._client = CosmosClient.from_connection_string(conn_str)
        elif end_pt:
            credential = DefaultAzureCredential()
            self._client = CosmosClient(url=end_pt, credential=credential)
        else:
            raise ValueError("Either connection_string or endpoint must be provided to CosmosService")

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

    # ------------------------------------------------------------------ #
    #  Device Token Management (for FCM)
    # ------------------------------------------------------------------ #

    def _get_device_tokens_container(self):
        """Get or create the DeviceTokens container."""
        if hasattr(self, '_device_tokens_container'):
            return self._device_tokens_container
        
        database = self._client.get_database_client(self._database_name)
        container_name = "DeviceTokens"
        
        try:
            container = database.get_container_client(container_name)
            # Test connection
            container.read()
        except Exception:
            # Container might not exist, create it
            try:
                container = database.create_container(
                    id=container_name,
                    partition_key="/userId",
                    default_ttl=-1  # Disable auto-expiry, we'll manage TTL ourselves
                )
            except Exception as e:
                logger.error(f"Failed to create DeviceTokens container: {e}")
                raise
        
        self._device_tokens_container = container
        return container

    async def register_device_token(
        self,
        user_id: str,
        fcm_token: str,
        platform: str = "android",
    ) -> bool:
        """Register or update an FCM device token for a user.
        
        Args:
            user_id: User ID from JWT subject claim
            fcm_token: Firebase Cloud Messaging token
            platform: Device platform (default: "android")
            
        Returns:
            True if registration successful, False otherwise
        """
        from models.documents import DeviceTokenDocument
        
        try:
            container = self._get_device_tokens_container()
            
            # Check if token already exists for this user
            query = (
                "SELECT * FROM c WHERE c.userId = @userId AND c.fcmToken = @fcmToken"
            )
            parameters = [
                {"name": "@userId", "value": user_id},
                {"name": "@fcmToken", "value": fcm_token},
            ]
            
            existing_tokens = list(container.query_items(
                query=query,
                parameters=parameters,
                partition_key=user_id,
            ))
            
            if existing_tokens:
                # Update existing token
                existing_doc = existing_tokens[0]
                existing_doc["lastActiveAt"] = datetime.now(timezone.utc).isoformat()
                container.replace_item(existing_doc["id"], existing_doc)
                logger.info(f"Updated existing device token for user {user_id}")
            else:
                # Create new token document
                token_doc = DeviceTokenDocument.new_token(
                    user_id=user_id,
                    fcm_token=fcm_token,
                    platform=platform,
                )
                container.create_item(token_doc.to_cosmos_dict())
                logger.info(f"Registered new device token for user {user_id}")
            
            return True
            
        except Exception as e:
            logger.exception(f"Error registering device token for user {user_id}: {e}")
            return False

    async def unregister_device_token(
        self,
        user_id: str,
        fcm_token: str,
    ) -> bool:
        """Unregister an FCM device token.
        
        Args:
            user_id: User ID from JWT subject claim
            fcm_token: Firebase Cloud Messaging token to unregister
            
        Returns:
            True if unregistration successful, False otherwise
        """
        try:
            container = self._get_device_tokens_container()
            
            # Find the token document
            query = (
                "SELECT * FROM c WHERE c.userId = @userId AND c.fcmToken = @fcmToken"
            )
            parameters = [
                {"name": "@userId", "value": user_id},
                {"name": "@fcmToken", "value": fcm_token},
            ]
            
            token_docs = list(container.query_items(
                query=query,
                parameters=parameters,
                partition_key=user_id,
            ))
            
            if not token_docs:
                logger.warning(f"No device token found for user {user_id} with token {fcm_token[:10]}...")
                return False
            
            # Delete the token document
            token_doc = token_docs[0]
            container.delete_item(token_doc["id"], partition_key=user_id)
            logger.info(f"Unregistered device token for user {user_id}")
            
            return True
            
        except Exception as e:
            logger.exception(f"Error unregistering device token for user {user_id}: {e}")
            return False

    async def get_user_device_tokens(
        self,
        user_id: str,
        exclude_expired: bool = True,
        days_threshold: int = 30,
    ) -> List[str]:
        """Get all FCM tokens for a user.
        
        Args:
            user_id: User ID from JWT subject claim
            exclude_expired: Whether to exclude expired tokens
            days_threshold: Number of days without activity to consider token expired
            
        Returns:
            List of FCM token strings
        """
        from models.documents import DeviceTokenDocument
        
        try:
            container = self._get_device_tokens_container()
            
            # Query all tokens for this user
            query = "SELECT * FROM c WHERE c.userId = @userId"
            parameters = [{"name": "@userId", "value": user_id}]
            
            token_items = list(container.query_items(
                query=query,
                parameters=parameters,
                partition_key=user_id,
            ))
            
            tokens = []
            for item in token_items:
                token_doc = DeviceTokenDocument.from_cosmos_dict(item)
                
                # Check if token is expired
                if exclude_expired and token_doc.is_expired(days_threshold):
                    logger.debug(f"Skipping expired token for user {user_id}")
                    continue
                
                tokens.append(token_doc.fcmToken)
            
            logger.debug(f"Found {len(tokens)} device tokens for user {user_id}")
            return tokens
            
        except Exception as e:
            logger.exception(f"Error getting device tokens for user {user_id}: {e}")
            return []

    async def cleanup_expired_tokens(
        self,
        days_threshold: int = 30,
    ) -> int:
        """Clean up expired device tokens.
        
        Args:
            days_threshold: Number of days without activity to consider token expired
            
        Returns:
            Number of tokens cleaned up
        """
        from datetime import datetime, timezone
        
        try:
            container = self._get_device_tokens_container()
            
            # Query all expired tokens
            cutoff_date = datetime.now(timezone.utc).isoformat()
            # Note: CosmosDB doesn't support complex date comparisons in queries,
            # so we'll need to fetch and filter in memory for small datasets
            
            query = "SELECT * FROM c"
            all_tokens = list(container.query_items(
                query=query,
                enable_cross_partition_query=True,
            ))
            
            expired_count = 0
            for token_item in all_tokens:
                token_doc = DeviceTokenDocument.from_cosmos_dict(token_item)
                if token_doc.is_expired(days_threshold):
                    try:
                        container.delete_item(
                            token_item["id"],
                            partition_key=token_doc.userId,
                        )
                        expired_count += 1
                        logger.debug(f"Cleaned up expired token for user {token_doc.userId}")
                    except Exception as e:
                        logger.error(f"Error deleting expired token {token_item['id']}: {e}")
            
            if expired_count > 0:
                logger.info(f"Cleaned up {expired_count} expired device tokens")
            
            return expired_count
            
        except Exception as e:
            logger.exception(f"Error cleaning up expired tokens: {e}")
            return 0
