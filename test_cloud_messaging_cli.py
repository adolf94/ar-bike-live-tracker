#!/usr/bin/env python3
"""
Dedicated Cloud Messaging Test Script
Use this for actual cloud messaging testing (Automate/FCM).
For simple broadcast testing only, use broadcast_test.py.
"""

import argparse
import asyncio
import json
import os
import sys
from pathlib import Path

# Add backend directory to Python path
backend_dir = Path(__file__).parent / "backend"
sys.path.insert(0, str(backend_dir))

from datetime import datetime
from models.documents import TelemetryDocument
from models.telemetry import EventType
from services.cloud_messaging_service import CloudMessagingService
from services.cosmos_service import CosmosService


def load_settings():
    """Load settings from local.settings.json."""
    settings_path = Path(__file__).parent / "backend" / "local.settings.json"
    settings = {}
    
    if settings_path.exists():
        try:
            with open(settings_path, 'r') as f:
                settings_data = json.load(f)
                settings = settings_data.get("Values", {})
        except Exception as e:
            print(f"Error loading settings: {e}")
    
    return settings


def show_quick_config(settings):
    """Show a quick configuration summary."""
    print("\n=== Quick Configuration Check ===")
    
    enable_cloud = settings.get("ENABLE_CLOUD_MESSAGING", "false").lower() == "true"
    automate_enabled = settings.get("AUTOMATE_ENABLED", "false").lower() == "true" and enable_cloud
    fcm_enabled = settings.get("FCM_ENABLED", "false").lower() == "true" and enable_cloud
    
    print(f"Cloud Messaging Enabled: {enable_cloud}")
    print(f"Automate Enabled: {automate_enabled}")
    print(f"FCM Enabled: {fcm_enabled}")
    
    if not enable_cloud:
        print("\n⚠ Set ENABLE_CLOUD_MESSAGING=true in local.settings.json")
    
    return enable_cloud, automate_enabled, fcm_enabled


async def test_configuration():
    """Test cloud messaging configuration."""
    print("=== Cloud Messaging Configuration Test ===")
    
    settings = load_settings()
    
    # Quick config check
    enable_cloud, automate_enabled, fcm_enabled = show_quick_config(settings)
    
    if not enable_cloud:
        print("\n✗ Cloud messaging disabled. Cannot proceed.")
        return None
    
    # Initialize CosmosService if needed for FCM
    cosmos_service = None
    if fcm_enabled:
        cosmos_conn_str = settings.get("CosmosDBConnectionString")
        cosmos_endpoint = settings.get("CosmosDBEndpoint", "")
        
        if cosmos_conn_str or cosmos_endpoint:
            try:
                cosmos_service = CosmosService(
                    connection_string=cosmos_conn_str,
                    endpoint=cosmos_endpoint,
                    database_name=settings.get("COSMOS_DATABASE_NAME", "AntigravityDb"),
                    container_name=settings.get("COSMOS_CONTAINER_NAME", "Telemetry"),
                )
                print("✓ CosmosService initialized (for FCM token management)")
            except Exception as e:
                print(f"⚠ CosmosService initialization failed: {e}")
                # Continue without CosmosService - FCM will be limited
    
    # Create CloudMessagingService
    try:
        messaging = CloudMessagingService.from_environment(
            automate_secret=settings.get("AUTOMATE_SECRET", ""),
            automate_to=settings.get("AUTOMATE_TO", ""),
            automate_device=settings.get("AUTOMATE_DEVICE", ""),
            fcm_project_id=settings.get("FCM_PROJECT_ID", ""),
            fcm_service_account_json=settings.get("FCM_SERVICE_ACCOUNT_JSON", ""),
            cosmos_service=cosmos_service,
        )
        
        print("\n✓ CloudMessagingService initialized")
        
        # Display provider status
        print(f"\n=== Provider Status ===")
        if messaging.automate_config.enabled:
            print(f"Automate: READY")
            print(f"  To: {settings.get('AUTOMATE_TO', 'Not set')}")
        else:
            print(f"Automate: NOT CONFIGURED (set AUTOMATE_ENABLED=true, AUTOMATE_SECRET, AUTOMATE_TO)")
        
        if messaging.fcm_config.enabled:
            print(f"FCM: READY")
            print(f"  Project: {settings.get('FCM_PROJECT_ID', 'Not set')}")
        else:
            print(f"FCM: NOT CONFIGURED (set FCM_ENABLED=true, FCM_PROJECT_ID, FCM_SERVICE_ACCOUNT_JSON)")
        
        return messaging
        
    except Exception as e:
        print(f"\n✗ CloudMessagingService initialization failed: {e}")
        import traceback
        traceback.print_exc()
        return None


async def send_test_notification(messaging, event_type_str, user_ids=None):
    """Send a test notification."""
    try:
        event_type = EventType(event_type_str)
    except ValueError:
        print(f"\n✗ Invalid event type '{event_type_str}'")
        print(f"Valid events: {[e.value for e in EventType]}")
        return False
    
    # Create test telemetry document
    telemetry_doc = TelemetryDocument(
        deviceId="test-device-001",
        status_updated_at=datetime.now().isoformat(),
        location={
            "lat": -6.2088,
            "lng": 106.8456,
            "course": 0,
        },
        status={
            "speed": 12.5 if event_type == EventType.UNAUTHORIZED_MOVEMENT else 0.0,
            "isIgnitionOn": event_type != EventType.UNAUTHORIZED_MOVEMENT,  # False for unauthorized movement
            "batteryLevel": 85,
            "isOnline": True,
        },
        eventTriggered=event_type.value,
        ttl=60 * 60 * 24 * 60,  # 60 days
    )
    
    print(f"\n=== Sending Test Notification ===")
    print(f"Event: {event_type.value}")
    print(f"Speed: {telemetry_doc.speed} km/h")
    print(f"Ignition: {telemetry_doc.is_ignition_on}")
    print(f"User IDs: {user_ids or 'None (FCM will be skipped if no tokens registered)'}")
    
    success, results = await messaging.send_event_notification(
        event_type=event_type,
        telemetry_doc=telemetry_doc,
        user_ids=user_ids or [],
    )
    
    print(f"\n=== Results ===")
    for provider, result in results.items():
        print(f"{provider}: {result}")
    
    if success:
        print(f"\n✓ Test notification successful (at least one provider succeeded)")
    else:
        print(f"\n⚠ Test notification partially or fully failed")
    
    return success


async def main():
    parser = argparse.ArgumentParser(
        description="Dedicated cloud messaging test script. "
                    "Use broadcast_test.py for simple broadcast testing only."
    )
    parser.add_argument("--event", type=str, default="unauthorized_movement",
                        help=f"Event type to test ({', '.join([e.value for e in EventType])})")
    parser.add_argument("--user-ids", type=str, default="",
                        help="Comma-separated user IDs for FCM testing")
    parser.add_argument("--list-events", action="store_true",
                        help="List all available event types")
    parser.add_argument("--config-only", action="store_true",
                        help="Only show configuration, don't send notifications")
    parser.add_argument("--quick", action="store_true",
                        help="Quick configuration check only")
    
    args = parser.parse_args()
    
    print("=" * 60)
    print("CLOUD MESSAGING TEST SCRIPT")
    print("=" * 60)
    
    if args.quick:
        settings = load_settings()
        show_quick_config(settings)
        return
    
    if args.list_events:
        print("\nAvailable event types:")
        for event_type in EventType:
            print(f"  {event_type.value}")
        return
    
    # Test configuration
    messaging = await test_configuration()
    
    if not messaging:
        print("\n✗ Cannot proceed - configuration failed")
        return
    
    # Check if any provider is enabled
    if not (messaging.automate_config.enabled or messaging.fcm_config.enabled):
        print("\n⚠ No cloud messaging providers are enabled!")
        print("Configure at least one of:")
        print("  - AUTOMATE_ENABLED=true with AUTOMATE_SECRET and AUTOMATE_TO")
        print("  - FCM_ENABLED=true with FCM_PROJECT_ID and FCM_SERVICE_ACCOUNT_JSON")
        return
    
    if args.config_only:
        return
    
    # Parse user IDs
    user_ids = None
    if args.user_ids:
        user_ids = [uid.strip() for uid in args.user_ids.split(",") if uid.strip()]
    
    # Send test notification
    await send_test_notification(messaging, args.event, user_ids)
    
    print("\n" + "=" * 60)
    print("Test complete!")
    print("\nFor simple broadcast testing (no cloud messaging):")
    print("  python broadcast_test.py --event unauthorized_movement")
    print("\nTo show cloud messaging configuration only:")
    print("  python broadcast_test.py --show-cloud-config")


if __name__ == "__main__":
    asyncio.run(main())