"""Firebase Cloud Messaging Service.

Sends push notifications to Android devices via Firebase Cloud Messaging.
"""

import json
import logging
import os
from typing import Dict, Any, List, Optional
from datetime import datetime

from models.documents import TelemetryDocument
from models.telemetry import EventType
from services.cloud_messaging_service import MessagePriority
from services.cosmos_service import CosmosService

logger = logging.getLogger(__name__)


class FcmService:
    """Service for sending notifications via Firebase Cloud Messaging."""
    
    # FCM API endpoint
    FCM_API_URL = "https://fcm.googleapis.com/v1/projects/{project_id}/messages:send"
    
    def __init__(
        self,
        project_id: str,
        service_account_json: str,
        cosmos_service: CosmosService,
    ):
        """Initialize FCM service.
        
        Args:
            project_id: Firebase project ID
            service_account_json: Path to Firebase service account JSON file
            cosmos_service: CosmosService instance for token management
        """
        self.project_id = project_id.strip()
        self.service_account_json = service_account_json.strip()
        self.cosmos_service = cosmos_service
        
        if not self.project_id:
            raise ValueError("Firebase project ID cannot be empty")
        if not self.service_account_json:
            raise ValueError("Firebase service account JSON path cannot be empty")
        
        # Load service account credentials
        self._credentials = self._load_credentials()
        self._access_token = None
        self._token_expiry = None
        
        logger.info(f"FcmService initialized for project {self.project_id}")
    
    def _load_credentials(self) -> Dict[str, Any]:
        """Load Firebase service account credentials."""
        try:
            # Try to load from file
            if os.path.exists(self.service_account_json):
                with open(self.service_account_json, 'r') as f:
                    return json.load(f)
            
            # Try to parse as JSON string (for environment variable)
            try:
                return json.loads(self.service_account_json)
            except json.JSONDecodeError:
                raise ValueError(f"Invalid service account JSON: {self.service_account_json[:50]}...")
                
        except Exception as e:
            logger.error(f"Failed to load Firebase credentials: {e}")
            raise
    
    async def _get_access_token(self) -> str:
        """Get OAuth2 access token for Firebase API.
        
        Returns:
            Access token string
        """
        import httpx
        from datetime import datetime, timezone
        
        # Check if token is still valid (with 5 minute buffer)
        if (self._access_token and self._token_expiry and 
            datetime.now(timezone.utc) < self._token_expiry):
            return self._access_token
        
        try:
            # Request new token from Google OAuth2 endpoint
            token_url = "https://oauth2.googleapis.com/token"
            
            payload = {
                "grant_type": "urn:ietf:params:oauth:grant-type:jwt-bearer",
                "assertion": self._create_jwt_assertion(),
            }
            
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.post(token_url, data=payload)
                response.raise_for_status()
                
                token_data = response.json()
                self._access_token = token_data["access_token"]
                # Set expiry with 5 minute buffer
                expires_in = token_data.get("expires_in", 3600)
                self._token_expiry = datetime.now(timezone.utc).timestamp() + expires_in - 300
                
                return self._access_token
                
        except Exception as e:
            logger.exception(f"Error getting Firebase access token: {e}")
            raise
    
    def _create_jwt_assertion(self) -> str:
        """Create JWT assertion for OAuth2 token request."""
        import jwt
        from datetime import datetime, timezone, timedelta
        
        creds = self._credentials
        
        # Create JWT payload
        now = datetime.now(timezone.utc)
        expiry = now + timedelta(hours=1)
        
        payload = {
            "iss": creds["client_email"],
            "scope": "https://www.googleapis.com/auth/firebase.messaging",
            "aud": "https://oauth2.googleapis.com/token",
            "exp": int(expiry.timestamp()),
            "iat": int(now.timestamp()),
        }
        
        # Sign with private key
        private_key = creds["private_key"].replace("\\n", "\n")
        assertion = jwt.encode(payload, private_key, algorithm="RS256")
        
        return assertion
    
    def _construct_fcm_payload(
        self,
        event_type: EventType,
        telemetry_doc: TelemetryDocument,
        fcm_token: str,
        priority: MessagePriority,
    ) -> Dict[str, Any]:
        """Construct FCM API payload.
        
        Args:
            event_type: Type of event that triggered notification
            telemetry_doc: Telemetry document containing event data
            fcm_token: Target FCM device token
            priority: Message priority level
            
        Returns:
            Payload dictionary ready for JSON serialization
        """
        # Format timestamp
        timestamp = telemetry_doc.timestamp
        if isinstance(timestamp, datetime):
            timestamp = timestamp.isoformat()
        
        # Data-only message (no notification block) for background handling
        message = {
            "token": fcm_token,
            "data": {
                "event": event_type.value,
                "deviceId": telemetry_doc.deviceId,
                "timestamp": timestamp,
                "speed": str(telemetry_doc.speed),
                "lat": str(telemetry_doc.location.get("lat", 0.0)),
                "lng": str(telemetry_doc.location.get("lng", 0.0)),
                "batteryLevel": str(telemetry_doc.status.get("batteryLevel", 0)),
                "isOnline": str(telemetry_doc.status.get("isOnline", True)),
                "isIgnitionOn": str(telemetry_doc.status.get("isIgnitionOn", False)),
            },
        }
        
        # Add Android-specific configuration
        if priority == MessagePriority.HIGH:
            message["android"] = {
                "priority": "high",
                "ttl": "0s",  # Deliver immediately, no queuing
            }
        else:
            message["android"] = {
                "priority": "normal",
            }
        
        # Wrap in FCM message format
        payload = {
            "message": message,
            "validate_only": False,  # Actually send the message
        }
        
        return payload
    
    async def send_event_notification(
        self,
        event_type: EventType,
        telemetry_doc: TelemetryDocument,
        user_ids: List[str],
        priority: MessagePriority,
    ) -> bool:
        """Send event notification via FCM to multiple users.
        
        Args:
            event_type: Type of event that triggered notification
            telemetry_doc: Telemetry document containing event data
            user_ids: List of user IDs to notify
            priority: Message priority level
            
        Returns:
            True if at least one notification was sent successfully, False otherwise
        """
        if not user_ids:
            logger.warning("No user IDs provided for FCM notification")
            return False
        
        try:
            # Get access token
            access_token = await self._get_access_token()
            
            # Get FCM tokens for all users
            all_tokens = []
            for user_id in user_ids:
                user_tokens = await self.cosmos_service.get_user_device_tokens(user_id)
                all_tokens.extend(user_tokens)
            
            if not all_tokens:
                logger.warning(f"No FCM tokens found for users: {user_ids}")
                return False
            
            # Send to each token
            success_count = 0
            for fcm_token in all_tokens:
                token_success = await self._send_to_token(
                    event_type=event_type,
                    telemetry_doc=telemetry_doc,
                    fcm_token=fcm_token,
                    priority=priority,
                    access_token=access_token,
                )
                if token_success:
                    success_count += 1
            
            if success_count > 0:
                logger.info(
                    f"FCM notification sent: {event_type.value} to "
                    f"{success_count}/{len(all_tokens)} tokens (priority: {priority.value})"
                )
                return True
            else:
                logger.error(f"Failed to send FCM notification to any tokens for event: {event_type.value}")
                return False
                
        except Exception as e:
            logger.exception(f"Error sending FCM notification: {e}")
            return False
    
    async def _send_to_token(
        self,
        event_type: EventType,
        telemetry_doc: TelemetryDocument,
        fcm_token: str,
        priority: MessagePriority,
        access_token: str,
    ) -> bool:
        """Send notification to a single FCM token."""
        import httpx
        
        try:
            # Construct payload
            payload = self._construct_fcm_payload(
                event_type=event_type,
                telemetry_doc=telemetry_doc,
                fcm_token=fcm_token,
                priority=priority,
            )
            
            # Send HTTP POST request
            url = self.FCM_API_URL.format(project_id=self.project_id)
            headers = {
                "Authorization": f"Bearer {access_token}",
                "Content-Type": "application/json",
            }
            
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.post(url, json=payload, headers=headers)
                
                # Check response
                if response.status_code == 200:
                    return True
                elif response.status_code == 404:
                    # Token not registered or invalid
                    logger.warning(f"FCM token invalid or not registered: {fcm_token[:10]}...")
                    # TODO: Mark token as invalid in CosmosDB for cleanup
                    return False
                elif response.status_code == 400:
                    logger.error(f"FCM API bad request: {response.text[:200]}")
                    return False
                elif response.status_code == 401:
                    logger.error("FCM API unauthorized - invalid credentials")
                    return False
                else:
                    logger.error(
                        f"FCM API error: status={response.status_code}, "
                        f"response={response.text[:200]}"
                    )
                    return False
                    
        except httpx.TimeoutException:
            logger.error("FCM API timeout")
            return False
        except httpx.RequestError as e:
            logger.error(f"FCM API request error: {e}")
            return False
        except Exception as e:
            logger.exception(f"Unexpected error sending FCM notification: {e}")
            return False
    
    async def send_test_notification(
        self,
        test_token: str,
    ) -> bool:
        """Send a test notification to verify FCM configuration.
        
        Args:
            test_token: FCM token to send test notification to
            
        Returns:
            True if test notification was sent successfully, False otherwise
        """
        from models.documents import TelemetryDocument, LocationInfo, StatusInfo
        
        # Create a mock telemetry document for testing
        mock_doc = TelemetryDocument(
            deviceId="test-device",
            status_updated_at=datetime.now().isoformat(),
            location={
                "lat": -6.2088,
                "lng": 106.8456,
                "course": 0,
            },
            status={
                "speed": 0.0,
                "isIgnitionOn": False,
                "batteryLevel": 85,
                "isOnline": True,
            },
            eventTriggered=EventType.UNAUTHORIZED_MOVEMENT.value,
            ttl=60 * 60 * 24 * 60,  # 60 days
        )
        
        logger.info(f"Sending FCM test notification to token: {test_token[:10]}...")
        
        # Mock sending to a single token
        try:
            access_token = await self._get_access_token()
            success = await self._send_to_token(
                event_type=EventType.UNAUTHORIZED_MOVEMENT,
                telemetry_doc=mock_doc,
                fcm_token=test_token,
                priority=MessagePriority.HIGH,
                access_token=access_token,
            )
            
            if success:
                logger.info("FCM test notification sent successfully")
            else:
                logger.error("FCM test notification failed")
                
            return success
            
        except Exception as e:
            logger.exception(f"Error sending FCM test notification: {e}")
            return False