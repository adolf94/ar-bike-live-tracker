import os
import logging
from typing import Optional, Dict, Any
from azure.cosmos import CosmosClient, PartitionKey
from models.order import Order

logger = logging.getLogger(__name__)

CONTAINER_NAME = "Orders"
HISTORY_CONTAINER_NAME = "OrderLocationHistory"


class OrderRepository:
    def __init__(
        self,
        connection_string: Optional[str] = None,
        endpoint: Optional[str] = None,
        database_name: Optional[str] = None,
        container_name: str = CONTAINER_NAME,
        history_container_name: str = HISTORY_CONTAINER_NAME
    ):
        self.conn_str = (connection_string or os.environ.get("CosmosDBConnectionString") or os.environ.get("COSMOS_DB_CONNECTION_STRING") or "").strip()
        self.endpoint = (endpoint or os.environ.get("CosmosDBEndpoint") or os.environ.get("COSMOS_DB_ENDPOINT") or "").strip()
        self.database_name = database_name or os.environ.get("COSMOS_DATABASE_NAME") or os.environ.get("COSMOS_DB_DATABASE_NAME") or "AntigravityDb"
        self.container_name = container_name
        self.history_container_name = history_container_name
        self._container = None
        self._history_container = None
        self._db = None

    def _get_db(self):
        if self._db is None:
            if self.conn_str:
                client = CosmosClient.from_connection_string(self.conn_str)
            elif self.endpoint:
                from azure.identity import DefaultAzureCredential
                client = CosmosClient(url=self.endpoint, credential=DefaultAzureCredential())
            else:
                client = CosmosClient(
                    "https://localhost:8081",
                    credential="C2y6yDjf5/R+ob0N8A7Cgv30VRDJIWEHLM+4QDU5DE2nQ9nDuVTqobD4b8mGGyPMbIZnqyMsEcaGQy67XIw/Jw=="
                )
            self._db = client.get_database_client(self.database_name)
        return self._db

    def _get_container(self):
        if self._container is None:
            db = self._get_db()
            try:
                self._container = db.create_container_if_not_exists(
                    id=self.container_name,
                    partition_key=PartitionKey(path="/tracking_id")
                )
            except Exception:
                self._container = db.get_container_client(self.container_name)
        return self._container

    def _get_history_container(self):
        if self._history_container is None:
            db = self._get_db()
            try:
                self._history_container = db.create_container_if_not_exists(
                    id=self.history_container_name,
                    partition_key=PartitionKey(path="/tracking_id")
                )
            except Exception:
                self._history_container = db.get_container_client(self.history_container_name)
        return self._history_container

    @property
    def container(self):
        return self._get_container()

    @property
    def history_container(self):
        return self._get_history_container()

    def create(self, order: Order) -> Dict[str, Any]:
        item = order.model_dump()
        return self.container.create_item(body=item)

    def get_by_tracking_id(self, tracking_id: str) -> Optional[Dict[str, Any]]:
        query = "SELECT * FROM c WHERE c.tracking_id = @tracking_id"
        parameters = [{"name": "@tracking_id", "value": tracking_id}]
        try:
            items = list(self.container.query_items(
                query=query,
                parameters=parameters,
                partition_key=tracking_id
            ))
            return items[0] if items else None
        except Exception as e:
            logger.exception("Error querying order by tracking_id %s: %s", tracking_id, e)
            return None

    def get_active_orders(self) -> list[Dict[str, Any]]:
        query = "SELECT * FROM c WHERE c.status = 'active'"
        try:
            return list(self.container.query_items(
                query=query,
                enable_cross_partition_query=True
            ))
        except Exception as e:
            logger.exception("Error querying active orders: %s", e)
            return []

    def get_latest_active_order(self) -> Optional[Dict[str, Any]]:
        query = "SELECT TOP 1 * FROM c WHERE c.status = 'active' ORDER BY c.created_at DESC"
        try:
            items = list(self.container.query_items(
                query=query,
                enable_cross_partition_query=True
            ))
            return items[0] if items else None
        except Exception as e:
            logger.exception("Error querying latest active order: %s", e)
            return None

    def get_by_id(self, order_id: str) -> Optional[Dict[str, Any]]:
        query = "SELECT * FROM c WHERE c.id = @order_id"
        parameters = [{"name": "@order_id", "value": order_id}]
        try:
            items = list(self.container.query_items(
                query=query,
                parameters=parameters,
                enable_cross_partition_query=True
            ))
            return items[0] if items else None
        except Exception as e:
            logger.exception("Error querying order by id %s: %s", order_id, e)
            return None

    def update(self, order_dict: Dict[str, Any]) -> Dict[str, Any]:
        return self.container.upsert_item(body=order_dict)

    def add_location_history(self, order_id: str, tracking_id: str, lat: float, lng: float, timestamp: str) -> Optional[Dict[str, Any]]:
        from models.order import OrderLocationHistory
        record = OrderLocationHistory(
            order_id=order_id,
            tracking_id=tracking_id,
            lat=lat,
            lng=lng,
            timestamp=timestamp
        )
        try:
            return self.history_container.create_item(body=record.model_dump())
        except Exception as e:
            logger.exception("Error saving location history for order %s: %s", order_id, e)
            return None

    def get_location_history(self, tracking_id: str) -> list[Dict[str, Any]]:
        query = "SELECT * FROM c WHERE c.tracking_id = @tracking_id ORDER BY c.timestamp ASC"
        parameters = [{"name": "@tracking_id", "value": tracking_id}]
        try:
            return list(self.history_container.query_items(
                query=query,
                parameters=parameters,
                partition_key=tracking_id
            ))
        except Exception as e:
            logger.exception("Error querying location history for tracking_id %s: %s", tracking_id, e)
            return []
