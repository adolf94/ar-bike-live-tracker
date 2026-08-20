from datetime import datetime, timezone
from typing import Optional
from pydantic import BaseModel, Field
import uuid
import secrets


class Location(BaseModel):
    lat: float
    lng: float
    timestamp: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())


class CreateOrderRequest(BaseModel):
    from_address: str
    to_address: str
    from_lat: Optional[float] = None
    from_lng: Optional[float] = None
    to_lat: Optional[float] = None
    to_lng: Optional[float] = None
    recipient_name: Optional[str] = None
    item_description: Optional[str] = None


class UpdateLocationRequest(BaseModel):
    lat: float
    lng: float


class UpdateStatusRequest(BaseModel):
    status: Optional[str] = None  # "active" | "completed" | "cancelled"
    delivery_stage: Optional[str] = None  # "going_to_pickup" | "going_to_dropoff" | "completed"


class Order(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    tracking_id: str = Field(default_factory=lambda: secrets.token_urlsafe(6).replace("-", "").replace("_", "")[:8].lower())
    from_address: str
    to_address: str
    from_coords: Optional[Location] = None
    to_coords: Optional[Location] = None
    recipient_name: Optional[str] = None
    item_description: Optional[str] = None
    status: str = "active"  # "active" | "completed" | "cancelled"
    delivery_stage: str = "going_to_pickup"  # "going_to_pickup" | "going_to_dropoff" | "completed"
    created_at: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    last_location: Optional[Location] = None


class OrderLocationHistory(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    order_id: str
    tracking_id: str
    lat: float
    lng: float
    timestamp: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
