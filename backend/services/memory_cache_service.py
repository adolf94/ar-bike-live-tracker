"""In-memory cache service for telemetry state with CosmosDB fallback."""

import asyncio
import logging
from datetime import datetime, timezone
from typing import List, Optional

from interfaces.i_state_store import IStateStore
from models.documents import TelemetryDocument
from services.cosmos_service import CosmosService

logger = logging.getLogger(__name__)


class MemoryCacheService(IStateStore):
    """In-memory cache for latest telemetry document with CosmosDB fallback.
    
    Implements IStateStore interface:
    - get_previous_state: Returns cached document, falls back to CosmosDB
    - get_history, get_events: Directly query CosmosDB (historical data)
    
    Thread-safe for Azure Functions concurrent access.
    """

    def __init__(self, cosmos_service: CosmosService):
        """Initialize cache with CosmosDB fallback service.
        
        Args:
            cosmos_service: CosmosService instance for fallback queries
        """
        self._cosmos = cosmos_service
        self._latest_document: Optional[TelemetryDocument] = None
        self._lock = asyncio.Lock()
        
    async def set_latest(self, document: TelemetryDocument) -> None:
        """Update the cached latest document.
        
        Thread-safe operation for concurrent access.
        
        Args:
            document: The latest TelemetryDocument to cache
        """
        async with self._lock:
            self._latest_document = document
            logger.debug(
                "Cache updated for device %s, id=%s",
                document.deviceId,
                document.id[:8] if document.id else "None"
            )

    async def get_previous_state(
        self, device_id: str
    ) -> Optional[TelemetryDocument]:
        """Return the most recent telemetry document for device_id.
        
        Implementation strategy:
        1. Return cached document if available
        2. Fallback: Query CosmosDB for latest document
        3. Cache and return CosmosDB result if found
        4. Return None if both cache and CosmosDB have no data
        
        Args:
            device_id: Device identifier
            
        Returns:
            Latest TelemetryDocument or None if no data exists
        """
        # 1. Try cache first
        async with self._lock:
            if self._latest_document is not None and self._latest_document.deviceId == device_id:
                logger.debug("Cache hit for device %s", device_id)
                return self._latest_document
        
        # 2. Cache miss - query CosmosDB
        logger.debug("Cache miss for device %s, querying CosmosDB", device_id)
        try:
            cosmos_doc = await self._cosmos.get_previous_state(device_id)
            if cosmos_doc is not None:
                # Cache the result for future requests
                async with self._lock:
                    self._latest_document = cosmos_doc
                    logger.debug(
                        "Cache populated from CosmosDB for device %s, id=%s",
                        device_id,
                        cosmos_doc.id[:8] if cosmos_doc.id else "None"
                    )
            return cosmos_doc
        except Exception as e:
            logger.exception("Error querying CosmosDB fallback for device %s", device_id)
            return None

    async def get_history(
        self, device_id: str, limit: int = 50, hours: int = 24
    ) -> List[TelemetryDocument]:
        """Return recent telemetry history.
        
        Historical data is not cached - always query CosmosDB.
        
        Args:
            device_id: Device identifier
            limit: Maximum records to return
            hours: Time window in hours
            
        Returns:
            List of TelemetryDocument objects
        """
        return await self._cosmos.get_history(device_id, limit=limit, hours=hours)

    async def get_events(
        self, device_id: str, limit: int = 20
    ) -> List[TelemetryDocument]:
        """Return recent documents where an event was triggered.
        
        Event history is not cached - always query CosmosDB.
        
        Args:
            device_id: Device identifier
            limit: Maximum events to return
            
        Returns:
            List of TelemetryDocument objects with events
        """
        return await self._cosmos.get_events(device_id, limit=limit)
    
    def get_cache_status(self) -> dict:
        """Return cache status for health monitoring.
        
        Returns:
            Dictionary with cache status information
        """
        if self._latest_document is None:
            return {
                "has_data": False,
                "device_id": None,
                "document_id": None,
                "timestamp": None
            }
        
        return {
            "has_data": True,
            "device_id": self._latest_document.deviceId,
            "document_id": self._latest_document.id[:8] + "..." if self._latest_document.id else None,
            "timestamp": self._latest_document.status_updated_at
        }