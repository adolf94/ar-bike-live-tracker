#!/usr/bin/env python3
"""
Test script for Cloud Messaging functionality.
Run this to verify Automate and FCM configurations.
"""

import os
import sys
import asyncio
from datetime import datetime
from pathlib import Path

# Add the backend directory to Python path
backend_dir = Path(__file__).parent
sys.path.insert(0, str(backend_dir))

from models.documents import TelemetryDocument, LocationInfo, StatusInfo
from models.telemetry import EventType
from services.cloud_messaging_service import CloudMessagingService, MessagePriority


async def test_cloud_messaging_config():
    """Test cloud messaging configuration and event filtering."""
    print("=== Cloud Messaging Configuration Test ===\n")
    
    # Load environment from local.settings.json
    env_file = backend_dir / "local.settings.json"
    if env_file.exists():
        import json
        with open(env_file, 'r') as f:
            settings = json.load(f)
            for key, value in settings["Values"].items():
                os.environ[key] = value
    
    # Create a mock telemetry document
    mock_doc = TelemetryDocument(
        deviceId="test-device-001",
        status_updated_at=datetime.now().isoformat(),
        location={
            "lat": -6.2088,
            "lng": 106.8456,
            "course": 0,
        },
        status={
            "speed": 12.5,
            "isIgnitionOn": False,  # For unauthorized_movement test
            "batteryLevel": 85,
            "isOnline": True,
        },
        eventTriggered=EventType.UNAUTHORIZED_MOVEMENT.value,
        ttl=60 * 60 * 24 * 60,  # 60 days
    )
    
    # Create CloudMessagingService from environment
    try:
        service = CloudMessagingService.from_environment(
            automate_secret=os.environ.get("AUTOMATE_SECRET", ""),
            automate_to=os.environ.get("AUTOMATE_TO", ""),
            automate_device=os.environ.get("AUTOMATE_DEVICE", ""),
            fcm_project_id=os.environ.get("FCM_PROJECT_ID", ""),
            fcm_service_account_json=os.environ.get("FCM_SERVICE_ACCOUNT_JSON", ""),
            cosmos_service=None,  # Not needed for config test
        )
        
        print("✓ CloudMessagingService initialized successfully")
        print(f"  Automate enabled: {service.automate_config.enabled}")
        print(f"  FCM enabled: {service.fcm_config.enabled}")
        
        if service.automate_config.enabled:
            print(f"\n  Automate configuration:")
            print(f"    High priority events: {[e.value for e in service.automate_config.high_priority_events]}")
            print(f"    Normal priority events: {[e.value for e in service.automate_config.normal_priority_events]}")
            if service.automate_config.enabled_events:
                print(f"    Enabled events: {[e.value for e in service.automate_config.enabled_events]}")
            else:
                print(f"    Enabled events: ALL (no filter)")
        
        if service.fcm_config.enabled:
            print(f"\n  FCM configuration:")
            print(f"    High priority events: {[e.value for e in service.fcm_config.high_priority_events]}")
            print(f"    Normal priority events: {[e.value for e in service.fcm_config.normal_priority_events]}")
            if service.fcm_config.enabled_events:
                print(f"    Enabled events: {[e.value for e in service.fcm_config.enabled_events]}")
            else:
                print(f"    Enabled events: ALL (no filter)")
        
        # Test event filtering for different event types
        print("\n=== Event Filtering Test ===")
        
        test_events = [
            EventType.UNAUTHORIZED_MOVEMENT,
            EventType.CONN_LOST,
            EventType.CONN_RESTORE,
            EventType.MOVEMENT_STARTED,
            EventType.MOVEMENT_STOPPED,
            EventType.ENGINE_OFF,
        ]
        
        for event_type in test_events:
            print(f"\nTesting event: {event_type.value}")
            
            # Check if should be sent via Automate
            automate_should_send = service._should_send_event(event_type, service.automate_config)
            automate_priority = service._determine_priority(event_type, service.automate_config)
            
            print(f"  Automate:")
            print(f"    Should send: {automate_should_send}")
            if automate_priority:
                print(f"    Priority: {automate_priority.value}")
            else:
                print(f"    Priority: Not in priority lists (won't be sent)")
            
            # Check if should be sent via FCM
            fcm_should_send = service._should_send_event(event_type, service.fcm_config)
            fcm_priority = service._determine_priority(event_type, service.fcm_config)
            
            print(f"  FCM:")
            print(f"    Should send: {fcm_should_send}")
            if fcm_priority:
                print(f"    Priority: {fcm_priority.value}")
            else:
                print(f"    Priority: Not in priority lists (won't be sent)")
        
        print("\n=== Configuration Summary ===")
        print("\nBased on your configuration:")
        
        # List events that will be sent
        print("\nEvents that will trigger notifications:")
        
        automate_events = []
        fcm_events = []
        
        for event_type in test_events:
            # Check Automate
            if (service.automate_config.enabled and 
                service._should_send_event(event_type, service.automate_config) and
                service._determine_priority(event_type, service.automate_config) is not None):
                automate_events.append(event_type.value)
            
            # Check FCM
            if (service.fcm_config.enabled and 
                service._should_send_event(event_type, service.fcm_config) and
                service._determine_priority(event_type, service.fcm_config) is not None):
                fcm_events.append(event_type.value)
        
        if automate_events:
            print(f"  Automate: {', '.join(automate_events)}")
        else:
            print(f"  Automate: No events configured (or service disabled)")
        
        if fcm_events:
            print(f"  FCM: {', '.join(fcm_events)}")
        else:
            print(f"  FCM: No events configured (or service disabled)")
        
        print("\n=== Configuration Notes ===")
        print("\nTo modify which events are sent:")
        print("1. Edit AUTOMATE_ENABLED_EVENTS in local.settings.json")
        print("2. Edit FCM_ENABLED_EVENTS in local.settings.json")
        print("\nTo modify event priorities:")
        print("1. Edit AUTOMATE_HIGH_PRIORITY_EVENTS in local.settings.json")
        print("2. Edit FCM_HIGH_PRIORITY_EVENTS in local.settings.json")
        print("3. Edit *_NORMAL_PRIORITY_EVENTS for normal priority events")
        
        return True
        
    except Exception as e:
        print(f"✗ Error: {e}")
        import traceback
        traceback.print_exc()
        return False


async def test_automate_service():
    """Test Automate service if configured."""
    print("\n=== Automate Service Test ===")
    
    automate_secret = os.environ.get("AUTOMATE_SECRET", "")
    automate_to = os.environ.get("AUTOMATE_TO", "")
    
    if not automate_secret or not automate_to:
        print("  Skipped: Automate credentials not configured")
        return None
    
    try:
        from services.automate_service import AutomateService
        
        service = AutomateService(
            secret=automate_secret,
            to_address=automate_to,
            device=os.environ.get("AUTOMATE_DEVICE", ""),
        )
        
        print("  ✓ AutomateService initialized")
        print(f"  To: {automate_to}")
        
        # Note: Uncomment to actually send a test notification
        # print("  Sending test notification...")
        # success = await service.send_test_notification()
        # if success:
        #     print("  ✓ Test notification sent successfully")
        # else:
        #     print("  ✗ Test notification failed")
        # return success
        
        print("  ⓘ Test notification sending commented out (uncomment to test)")
        return None
        
    except Exception as e:
        print(f"  ✗ Error: {e}")
        return False


async def main():
    """Main test function."""
    print("Cloud Messaging Feature Test")
    print("=" * 50)
    
    # Check environment
    enable_cloud_messaging = os.environ.get("ENABLE_CLOUD_MESSAGING", "false").lower() == "true"
    if not enable_cloud_messaging:
        print("⚠  Cloud messaging is disabled (ENABLE_CLOUD_MESSAGING=false)")
        print("   Set ENABLE_CLOUD_MESSAGING=true in local.settings.json to enable")
    
    # Run tests
    config_ok = await test_cloud_messaging_config()
    
    if config_ok:
        await test_automate_service()
    
    print("\n" + "=" * 50)
    print("Test completed")
    
    if config_ok:
        print("✓ Configuration is valid")
        print("\nNext steps:")
        print("1. Configure AUTOMATE_SECRET and AUTOMATE_TO for Automate notifications")
        print("2. Configure FCM_PROJECT_ID and FCM_SERVICE_ACCOUNT_JSON for FCM")
        print("3. Adjust event filtering in local.settings.json as needed")
        print("4. Deploy and test with real events")
    else:
        print("✗ Configuration has errors")


if __name__ == "__main__":
    asyncio.run(main())