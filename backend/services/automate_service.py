"""LlamaLabs Automate Cloud Messaging Service.

Sends notifications to Android devices via LlamaLabs Automate webhooks.
"""

import logging
import httpx
from typing import Dict, Any
from datetime import datetime

from models.documents import TelemetryDocument
from models.telemetry import EventType
from services.cloud_messaging_service import MessagePriority

logger = logging.getLogger(__name__)

# Constants
AUTOMATE_API_URL = "https://llamalab.com/automate/cloud/message"


class AutomateService:
    """Service for sending notifications via LlamaLabs Automate."""
    
    def __init__(self, secret: str, to_address: str, device: str = ""):
        """Initialize Automate service.
        
        Args:
            secret: LlamaLabs Automate secret key
            to_address: Recipient email/account
            device: Optional device identifier
        """
        self.secret = secret.strip()
        self.to_address = to_address.strip()
        self.device = device.strip()
        
        if not self.secret:
            raise ValueError("Automate secret cannot be empty")
        if not self.to_address:
            raise ValueError("Automate to_address cannot be empty")
        
        logger.info(f"AutomateService initialized for {self.to_address}")
    
    def _construct_payload(
        self,
        event_type: EventType,
        telemetry_doc: TelemetryDocument,
        priority: MessagePriority,
    ) -> Dict[str, Any]:
        """Construct Automate API payload.
        
        Args:
            event_type: Type of event that triggered notification
            telemetry_doc: Telemetry document containing event data
            priority: Message priority level
            
        Returns:
            Payload dictionary ready for JSON serialization
        """
        payload = {
            "secret": self.secret,
            "to": self.to_address,
            "priority": priority.value,
            "payload": {
                "event": event_type.value,
                "deviceId": telemetry_doc.device_id,
                "timestamp": telemetry_doc.timestamp.isoformat() if isinstance(telemetry_doc.timestamp, datetime) else telemetry_doc.timestamp,
                "speed": telemetry_doc.status.speed,
                "lat": telemetry_doc.location.lat,
                "lng": telemetry_doc.location.lng,
                "batteryLevel": telemetry_doc.status.battery_level,
                "isOnline": telemetry_doc.status.is_online,
                "isIgnitionOn": telemetry_doc.status.is_ignition_on,
            }
        }
        
        # Add optional device field if specified
        if self.device:
            payload["device"] = self.device
        
        return payload
    
    async def send_event_notification(
        self,
        event_type: EventType,
        telemetry_doc: TelemetryDocument,
        priority: MessagePriority,
    ) -> bool:
        """Send event notification via Automate webhook.
        
        Args:
            event_type: Type of event that triggered notification
            telemetry_doc: Telemetry document containing event data
            priority: Message priority level
            
        Returns:
            True if notification was sent successfully, False otherwise
        """
        try:
            # Construct payload
            payload = self._construct_payload(event_type, telemetry_doc, priority)
            
            # Send HTTP POST request
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.post(
                    AUTOMATE_API_URL,
                    json=payload,
                    headers={"Content-Type": "application/json"}
                )
                
                # Check response
                if response.status_code == GaleError.GONE:
                    # 410 Gone - likely means the Automate flow was deleted
                    logger.error(f"Automate API returned 410 Gone. Flow may have been deleted.")
                    return False
                elif response.status_code == 401:
                    # 401 Unauthorized - invalid secret
                    logger.error(f"Automate API returned 401 Unauthorized. Check secret key.")
                    return False
                elif response.status_code == 200:
                    logger.info(f"Automate notification sent: {event_type.value} (priority: {priority.value})")
                    return True
                else:
                    logger.error(
                        f"Automate API error: status={response.status_code}, "
                        f"response={response.text[:200]}"
                    )
                    return False
                    
        except httpx.TimeoutException:
            logger.error("Automate API timeout")
            return False
        except httpx.RequestError as e:
            logger.error(f"Automate API request error: {e}")
            return False
        except Exception as e:
            logger.exception(f"Unexpected error sending Automate notification: {e}")
            return False
    
    async def send_test_notification(self) -> bool:
        """Send a test notification to verify Automate configuration.
        
        Returns:
            True if test notification was sent successfully, False otherwise
        """
        from models.documents import TelemetryDocument, LocationInfo, StatusInfo
        
        # Create a mock telemetry document for testing
        mock_doc = TelemetryDocument(
            device_id="test-device",
            timestamp=datetime.now().isoformat(),
            location=LocationInfo(
                lat=-6.2088,
                lng=106.8456,
                course=0,
            ),
            status=StatusInfo(
                speed=0.0,
                is_ignition_on=False,
                battery_level=85,
                is_online=True,
            ),
            event_triggered=EventType.UNAUTHORIZED_MOVEMENT,
            ttl=60 * 60 * 24 * 60,  # 60 days
        )
        
        logger.info("Sending Automate test notification...")
        
        success = await self.send_event_notification(
            event_type=EventType.UNAUTHORIZED_MOVEMENT,
            telemetry_doc=mock_doc,
            priority=MessagePriority.HIGH,
        )
        
        if success:
            logger.info("Automate test notification sent successfully")
        else:
            logger.error("Automate test notification failed")
            
        return success