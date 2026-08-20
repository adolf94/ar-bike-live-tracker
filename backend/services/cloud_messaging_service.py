"""Cloud Messaging Service Orchestrator.

This service coordinates multiple cloud messaging providers (Automate, FCM)
based on configuration and event priorities.
"""

import logging
from enum import Enum
from typing import Dict, List, Optional, Set, Tuple
from dataclasses import dataclass

from models.documents import TelemetryDocument
from models.telemetry import EventType

logger = logging.getLogger(__name__)


class MessagePriority(str, Enum):
    """Message priority levels for cloud notifications."""
    HIGH = "high"
    NORMAL = "normal"


@dataclass
class NotificationConfig:
    """Configuration for cloud messaging notifications."""
    enabled: bool
    high_priority_events: Set[EventType]
    normal_priority_events: Set[EventType]
    enabled_events: Optional[Set[EventType]] = None  # If None, all events are enabled
    

class CloudMessagingService:
    """Orchestrates cloud messaging across multiple providers."""
    
    # Default priority mappings
    DEFAULT_HIGH_PRIORITY_EVENTS = {
        EventType.UNAUTHORIZED_MOVEMENT,
        EventType.CONN_LOST,
    }
    
    DEFAULT_NORMAL_PRIORITY_EVENTS = {
        EventType.MOVEMENT_STARTED,
        EventType.MOVEMENT_STOPPED,
        EventType.ENGINE_OFF,
        EventType.CONN_RESTORE,
    }
    
    def __init__(
        self,
        automate_service: Optional["AutomateService"] = None,
        fcm_service: Optional["FcmService"] = None,
        automate_config: Optional[NotificationConfig] = None,
        fcm_config: Optional[NotificationConfig] = None,
    ):
        """Initialize the cloud messaging orchestrator.
        
        Args:
            automate_service: Optional Automate service instance
            fcm_service: Optional FCM service instance
            automate_config: Configuration for Automate notifications
            fcm_config: Configuration for FCM notifications
        """
        self.automate_service = automate_service
        self.fcm_service = fcm_service
        
        # Set up configurations with defaults
        self.automate_config = automate_config or NotificationConfig(
            enabled=False,
            high_priority_events=self.DEFAULT_HIGH_PRIORITY_EVENTS,
            normal_priority_events=self.DEFAULT_NORMAL_PRIORITY_EVENTS,
        )
        
        self.fcm_config = fcm_config or NotificationConfig(
            enabled=False,
            high_priority_events=self.DEFAULT_HIGH_PRIORITY_EVENTS,
            normal_priority_events=self.DEFAULT_NORMAL_PRIORITY_EVENTS,
        )
        
        self._validate_priorities()
    
    def _validate_priorities(self):
        """Validate that events are assigned to exactly one priority level."""
        for config_name, config in [("automate", self.automate_config), 
                                   ("fcm", self.fcm_config)]:
            if not config.enabled:
                continue
                
            high_set = config.high_priority_events
            normal_set = config.normal_priority_events
            
            # Check for overlap
            overlap = high_set.intersection(normal_set)
            if overlap:
                logger.warning(
                    f"{config_name} config has overlapping priority events: {overlap}"
                )
    
    def _should_send_event(self, event_type: EventType, config: NotificationConfig) -> bool:
        """Check if an event should be sent based on configuration."""
        if not config.enabled:
            return False
        
        # If no specific enabled_events list, send all events
        if config.enabled_events is None:
            return True
        
        # Otherwise, only send if event is in enabled_events
        return event_type in config.enabled_events
    
    def _determine_priority(self, event_type: EventType, config: NotificationConfig) -> Optional[MessagePriority]:
        """Determine message priority based on event type and configuration.
        
        Returns None if event should not be sent (not in priority lists).
        """
        if event_type in config.high_priority_events:
            return MessagePriority.HIGH
        elif event_type in config.normal_priority_events:
            return MessagePriority.NORMAL
        else:
            # Event not in priority configuration
            return None
    
    async def send_event_notification(
        self,
        event_type: EventType,
        telemetry_doc: TelemetryDocument,
        user_ids: Optional[List[str]] = None,
    ) -> Tuple[bool, Dict[str, str]]:
        """Send event notification through all enabled cloud messaging providers.
        
        Args:
            event_type: Type of event that triggered the notification
            telemetry_doc: Telemetry document containing event data
            user_ids: Optional list of user IDs to notify (for FCM)
            
        Returns:
            Tuple of (overall_success, provider_results)
            provider_results: Dict mapping provider name to status/error message
        """
        provider_results = {}
        overall_success = False
        
        # Check if cloud messaging is enabled
        if not (self.automate_config.enabled or self.fcm_config.enabled):
            logger.debug("Cloud messaging disabled for all providers")
            return False, {"disabled": "All providers disabled"}
        
        # Send via Automate if enabled
        automate_result = await self._send_automate_notification(event_type, telemetry_doc)
        provider_results["automate"] = automate_result
        
        # Send via FCM if enabled and user_ids provided
        fcm_result = await self._send_fcm_notification(event_type, telemetry_doc, user_ids)
        provider_results["fcm"] = fcm_result
        
        # Overall success if at least one provider succeeded
        overall_success = any(
            result.startswith("success") 
            for result in provider_results.values() 
            if isinstance(result, str)
        )
        
        return overall_success, provider_results
    
    async def _send_automate_notification(
        self,
        event_type: EventType,
        telemetry_doc: TelemetryDocument,
    ) -> str:
        """Send notification via Automate webhook."""
        if not self.automate_config.enabled or not self.automate_service:
            return "disabled"
        
        # Check if this event should be sent via Automate
        if not self._should_send_event(event_type, self.automate_config):
            return "filtered: event not enabled"
        
        try:
            priority = self._determine_priority(event_type, self.automate_config)
            if priority is None:
                return "filtered: event not in priority lists"
            
            success = await self.automate_service.send_event_notification(
                event_type=event_type,
                telemetry_doc=telemetry_doc,
                priority=priority,
            )
            
            if success:
                return f"success: priority={priority.value}"
            else:
                return "failed: automateservice returned False"
                
        except Exception as e:
            logger.exception(f"Error sending Automate notification: {e}")
            return f"error: {str(e)}"
    
    async def _send_fcm_notification(
        self,
        event_type: EventType,
        telemetry_doc: TelemetryDocument,
        user_ids: Optional[List[str]] = None,
    ) -> str:
        """Send notification via Firebase Cloud Messaging."""
        if not self.fcm_config.enabled or not self.fcm_service:
            return "disabled"
        
        if not user_ids:
            logger.debug("FCM notification skipped: no user_ids provided")
            return "skipped: no user_ids"
        
        # Check if this event should be sent via FCM
        if not self._should_send_event(event_type, self.fcm_config):
            return "filtered: event not enabled"
        
        try:
            priority = self._determine_priority(event_type, self.fcm_config)
            if priority is None:
                return "filtered: event not in priority lists"
            
            success = await self.fcm_service.send_event_notification(
                event_type=event_type,
                telemetry_doc=telemetry_doc,
                user_ids=user_ids,
                priority=priority,
            )
            
            if success:
                return f"success: priority={priority.value}, users={len(user_ids)}"
            else:
                return "failed: fcmservice returned False"
                
        except Exception as e:
            logger.exception(f"Error sending FCM notification: {e}")
            return f"error: {str(e)}"
    
    @classmethod
    def from_environment(
        cls,
        automate_secret: str = "",
        automate_to: str = "",
        automate_device: str = "",
        fcm_project_id: str = "",
        fcm_service_account_json: str = "",
        cosmos_service: Optional["CosmosService"] = None,
    ) -> "CloudMessagingService":
        """Create CloudMessagingService instance from environment variables.
        
        Args:
            automate_secret: LlamaLabs Automate secret key
            automate_to: Recipient email/account
            automate_device: Device identifier
            fcm_project_id: Firebase project ID
            fcm_service_account_json: Path to Firebase service account JSON
            cosmos_service: CosmosService instance for FCM token management
            
        Returns:
            Configured CloudMessagingService instance
        """
        import os
        
        # Read configuration flags
        enable_cloud_messaging = os.environ.get("ENABLE_CLOUD_MESSAGING", "false").lower() == "true"
        automate_enabled = os.environ.get("AUTOMATE_ENABLED", "false").lower() == "true" and enable_cloud_messaging
        fcm_enabled = os.environ.get("FCM_ENABLED", "false").lower() == "true" and enable_cloud_messaging
        
        # Initialize services
        automate_service = None
        fcm_service = None
        
        if automate_enabled and automate_secret and automate_to:
            try:
                from .automate_service import AutomateService
                automate_service = AutomateService(
                    secret=automate_secret,
                    to_address=automate_to,
                    device=automate_device,
                )
                logger.info("AutomateService initialized")
            except ImportError:
                logger.warning("AutomateService not available")
        
        if fcm_enabled and fcm_project_id and fcm_service_account_json and cosmos_service:
            try:
                from .fcm_service import FcmService
                fcm_service = FcmService(
                    project_id=fcm_project_id,
                    service_account_json=fcm_service_account_json,
                    cosmos_service=cosmos_service,
                )
                logger.info("FcmService initialized")
            except ImportError:
                logger.warning("FcmService not available")
        
        # Parse priority configuration from environment
        automate_high_priority = cls._parse_event_list_from_env("AUTOMATE_HIGH_PRIORITY_EVENTS")
        automate_normal_priority = cls._parse_event_list_from_env("AUTOMATE_NORMAL_PRIORITY_EVENTS")
        fcm_high_priority = cls._parse_event_list_from_env("FCM_HIGH_PRIORITY_EVENTS")
        fcm_normal_priority = cls._parse_event_list_from_env("FCM_NORMAL_PRIORITY_EVENTS")
        
        # Parse enabled events configuration (if empty, all events are enabled)
        automate_enabled_events = cls._parse_event_list_from_env("AUTOMATE_ENABLED_EVENTS")
        fcm_enabled_events = cls._parse_event_list_from_env("FCM_ENABLED_EVENTS")
        
        # Create configurations
        automate_config = NotificationConfig(
            enabled=automate_enabled,
            high_priority_events=automate_high_priority or cls.DEFAULT_HIGH_PRIORITY_EVENTS,
            normal_priority_events=automate_normal_priority or cls.DEFAULT_NORMAL_PRIORITY_EVENTS,
            enabled_events=automate_enabled_events,  # None means all events enabled
        )
        
        fcm_config = NotificationConfig(
            enabled=fcm_enabled,
            high_priority_events=fcm_high_priority or cls.DEFAULT_HIGH_PRIORITY_EVENTS,
            normal_priority_events=fcm_normal_priority or cls.DEFAULT_NORMAL_PRIORITY_EVENTS,
            enabled_events=fcm_enabled_events,  # None means all events enabled
        )
        
        return cls(
            automate_service=automate_service,
            fcm_service=fcm_service,
            automate_config=automate_config,
            fcm_config=fcm_config,
        )
    
    @staticmethod
    def _parse_event_list_from_env(env_var: str) -> Optional[Set[EventType]]:
        """Parse comma-separated list of event types from environment variable."""
        import os
        
        value = os.environ.get(env_var, "").strip()
        if not value:
            return None
        
        events = set()
        for event_str in value.split(","):
            event_str = event_str.strip()
            if not event_str:
                continue
                
            try:
                event_type = EventType(event_str)
                events.add(event_type)
            except ValueError:
                logger.warning(f"Invalid event type '{event_str}' in {env_var}")
        
        return events if events else None