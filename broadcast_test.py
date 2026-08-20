import argparse
import asyncio
import json
import os
import sys

# Ensure backend directory is in python path to import services/models correctly
sys.path.append(os.path.join(os.path.dirname(__file__), 'backend'))

from services.broadcast_service import BroadcastService


def load_settings():
    """Load settings from .env files and local.settings.json."""
    settings = {}
    
    # Try loading from any .env files in the workspace
    for path in [".env", "backend/.env", "frontend/.env"]:
        full_path = os.path.join(os.path.dirname(__file__), path)
        if os.path.exists(full_path):
            try:
                with open(full_path, "r") as f:
                    for line in f:
                        line = line.strip()
                        if not line or line.startswith("#"):
                            continue
                        if "=" in line:
                            k, v = line.split("=", 1)
                            settings[k.strip()] = v.strip().strip('"').strip("'")
            except Exception as err:
                print(f"Warning: Could not parse {path}: {err}")
    
    # Load from local.settings.json
    settings_path = os.path.join(os.path.dirname(__file__), "backend", "local.settings.json")
    if os.path.exists(settings_path):
        try:
            with open(settings_path, "r") as f:
                settings_data = json.load(f)
                # Merge with existing settings (JSON takes precedence)
                for key, value in settings_data.get("Values", {}).items():
                    settings[key] = value
        except Exception as err:
            print(f"Warning: Could not parse local.settings.json: {err}")
    
    # Set defaults if not found
    if "WebPubSubConnectionString" not in settings:
        settings["WebPubSubConnectionString"] = "Endpoint=http://localhost;Port=8888;AccessKey=ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789ABCDEFGH;Version=1.0;"
    
    return settings


def show_cloud_messaging_config(settings):
    """Display cloud messaging configuration without heavy dependencies."""
    print("\n=== Cloud Messaging Configuration ===")
    
    # Check basic configuration
    enable_cloud = settings.get("ENABLE_CLOUD_MESSAGING", "false").lower() == "true"
    automate_enabled = settings.get("AUTOMATE_ENABLED", "false").lower() == "true" and enable_cloud
    fcm_enabled = settings.get("FCM_ENABLED", "false").lower() == "true" and enable_cloud
    
    if not enable_cloud:
        print("⚠ Cloud messaging is DISABLED (ENABLE_CLOUD_MESSAGING=false)")
        return
    
    print(f"Master switch: ENABLE_CLOUD_MESSAGING={enable_cloud}")
    
    # Automate configuration
    print(f"\nAutomate:")
    print(f"  Enabled: {automate_enabled}")
    if automate_enabled:
        automate_secret = settings.get("AUTOMATE_SECRET", "")
        automate_to = settings.get("AUTOMATE_TO", "")
        print(f"  To: {automate_to if automate_to else 'Not configured'}")
        print(f"  Secret: {'Configured' if automate_secret else 'Not configured'}")
        
        # Parse enabled events
        automate_events = settings.get("AUTOMATE_ENABLED_EVENTS", "")
        if automate_events:
            print(f"  Enabled events: {automate_events}")
        else:
            print(f"  Enabled events: ALL (no filter)")
    
    # FCM configuration
    print(f"\nFCM:")
    print(f"  Enabled: {fcm_enabled}")
    if fcm_enabled:
        fcm_project = settings.get("FCM_PROJECT_ID", "")
        fcm_service_account = settings.get("FCM_SERVICE_ACCOUNT_JSON", "")
        print(f"  Project ID: {fcm_project if fcm_project else 'Not configured'}")
        print(f"  Service Account: {'Configured' if fcm_service_account else 'Not configured'}")
        
        # Parse enabled events
        fcm_events = settings.get("FCM_ENABLED_EVENTS", "")
        if fcm_events:
            print(f"  Enabled events: {fcm_events}")
        else:
            print(f"  Enabled events: ALL (no filter)")
    
    # Show priority configuration
    print(f"\nHigh Priority Events (wake device, bypass DND):")
    automate_high = settings.get("AUTOMATE_HIGH_PRIORITY_EVENTS", "unauthorized_movement,conn_lost")
    fcm_high = settings.get("FCM_HIGH_PRIORITY_EVENTS", "unauthorized_movement,conn_lost")
    print(f"  Automate: {automate_high}")
    print(f"  FCM: {fcm_high}")
    
    print(f"\nNote: Use test_cloud_messaging_cli.py for full testing")


async def main():
    parser = argparse.ArgumentParser(
        description="Broadcast simulated telemetry events to Web PubSub / SignalR. "
                    "Optionally show cloud messaging configuration."
    )
    parser.add_argument("-e", "--event", type=str, default="movement_started",
                        help="Event name to trigger (e.g. movement_started, movement_stopped, "
                             "unauthorized_movement, engine_off, conn_lost, conn_restore)")
    parser.add_argument("-s", "--speed", type=float, default=45.0, help="Simulated speed (km/h)")
    parser.add_argument("--lat", type=float, default=14.55043, help="Simulated latitude")
    parser.add_argument("--lng", type=float, default=121.07967, help="Simulated longitude")
    parser.add_argument("-i", "--ignition", type=str, default="true", choices=["true", "false"],
                        help="Ignition state (true or false)")
    parser.add_argument("--show-cloud-config", action="store_true",
                        help="Show cloud messaging configuration without testing")
    parser.add_argument("--test-cloud", action="store_true",
                        help="Test cloud messaging after broadcast (uses cloud_test_cli.py approach)")
    
    args = parser.parse_args()
    
    # Load settings
    settings = load_settings()
    
    # Show cloud messaging configuration if requested
    if args.show_cloud_config:
        show_cloud_messaging_config(settings)
        print("\n" + "=" * 50)
        print("Note: This only shows configuration. Use test_cloud_messaging_cli.py for actual testing.")
        return
    
    # Get connection string
    conn_str = settings.get("WebPubSubConnectionString")
    hub_name = "telemetry_hub"
    
    # Create broadcast service
    svc = BroadcastService(conn_str, hub_name)
    
    # Create payload
    payload = {
        "id": "test-broadcast-id",
        "deviceId": "17026310059",
        "status_updated_at": "2026-07-12T15:00:00Z",
        "location": {
            "lat": args.lat,
            "lng": args.lng,
            "course": 45,
            "position_time": "2026-07-12 15:00:00"
        },
        "status": {
            "speed": args.speed,
            "isIgnitionOn": args.ignition.lower() == "true",
            "batteryLevel": 95,
            "isOnline": True
        },
        "eventTriggered": args.event if args.event.lower() != "none" else None,
        "ttl": 5184000
    }
    
    print(f"Broadcasting event '{args.event}' (speed: {args.speed} km/h, ignition: {args.ignition}) to hub '{hub_name}'...")
    await svc.broadcast_event(payload)
    print("Broadcast finished!")
    
    # Test cloud messaging if requested
    if args.test_cloud and args.event != "none":
        await test_cloud_messaging(settings, args)
    
    # Briefly mention cloud messaging if enabled but not tested
    elif not args.test_cloud:
        enable_cloud = settings.get("ENABLE_CLOUD_MESSAGING", "false").lower() == "true"
        if enable_cloud and args.event != "none":
            print(f"\nℹ Cloud messaging is ENABLED")
            print(f"  This event would trigger cloud notifications if it matches enabled events")
            print(f"  Use --test-cloud to test or --show-cloud-config to see configuration")


async def test_cloud_messaging(settings, args):
    """Test cloud messaging after broadcast."""
    print(f"\n" + "=" * 50)
    print("TESTING CLOUD MESSAGING")
    print("=" * 50)
    
    # Check if cloud messaging is enabled
    enable_cloud = settings.get("ENABLE_CLOUD_MESSAGING", "false").lower() == "true"
    if not enable_cloud:
        print("✗ Cloud messaging is DISABLED")
        print("Set ENABLE_CLOUD_MESSAGING=true in local.settings.json")
        return
    
    # Import event type
    try:
        from models.telemetry import EventType
        event_type = EventType(args.event)
    except ValueError:
        print(f"⚠ Event '{args.event}' is not a valid EventType")
        print(f"Valid events: {[e.value for e in EventType]}")
        return
    
    # Create mock telemetry document
    from datetime import datetime
    from models.documents import TelemetryDocument
    
    telemetry_doc = TelemetryDocument(
        deviceId="17026310059",
        status_updated_at=datetime.now().isoformat(),
        location={
            "lat": args.lat,
            "lng": args.lng,
            "course": 45,
        },
        status={
            "speed": args.speed,
            "isIgnitionOn": args.ignition.lower() == "true",
            "batteryLevel": 95,
            "isOnline": True,
        },
        eventTriggered=args.event,
        ttl=5184000,
    )
    
    print(f"Event: {event_type.value}")
    print(f"Speed: {args.speed} km/h")
    print(f"Ignition: {args.ignition}")
    print(f"Location: {args.lat}, {args.lng}")
    
    # Check which providers are enabled
    automate_enabled = settings.get("AUTOMATE_ENABLED", "false").lower() == "true"
    fcm_enabled = settings.get("FCM_ENABLED", "false").lower() == "true"
    
    print(f"\n=== Testing Providers ===")
    
    # Test Automate if enabled
    if automate_enabled:
        print(f"\nAutomate:")
        await test_automate_simple(settings, event_type, telemetry_doc)
    else:
        print(f"\nAutomate: DISABLED (set AUTOMATE_ENABLED=true)")
    
    # Test FCM if enabled
    if fcm_enabled:
        print(f"\nFCM:")
        print(f"  ⓘ FCM testing requires database connection")
        print(f"  Use cloud_test_cli.py --fcm --fcm-token YOUR_TOKEN for FCM testing")
    else:
        print(f"\nFCM: DISABLED (set FCM_ENABLED=true)")
    
    print(f"\nNote: For full FCM testing, use:")
    print(f"  python cloud_test_cli.py --event {args.event} --fcm --fcm-token YOUR_TOKEN")


async def test_automate_simple(settings, event_type, telemetry_doc):
    """Simple Automate test without database dependencies."""
    try:
        from services.automate_service import AutomateService
        from services.cloud_messaging_service import MessagePriority
        
        automate_secret = settings.get("AUTOMATE_SECRET", "")
        automate_to = settings.get("AUTOMATE_TO", "")
        
        if not automate_secret or not automate_to:
            print(f"  ✗ Not configured (missing AUTOMATE_SECRET or AUTOMATE_TO)")
            return
        
        print(f"  ✓ Configured for {automate_to}")
        
        # Create Automate service
        automate_service = AutomateService(
            secret=automate_secret,
            to_address=automate_to,
            device=settings.get("AUTOMATE_DEVICE", ""),
        )
        
        # Determine priority
        automate_high_priority = settings.get("AUTOMATE_HIGH_PRIORITY_EVENTS", "unauthorized_movement,conn_lost")
        high_priority_events = [e.strip() for e in automate_high_priority.split(",")]
        
        priority = MessagePriority.HIGH if event_type.value in high_priority_events else MessagePriority.NORMAL
        
        print(f"  Sending {event_type.value} with priority {priority.value}...")
        
        # Send test notification
        success = await automate_service.send_event_notification(
            event_type=event_type,
            telemetry_doc=telemetry_doc,
            priority=priority,
        )
        
        if success:
            print(f"  ✓ Notification sent successfully")
        else:
            print(f"  ✗ Notification failed")
        
    except ImportError as e:
        print(f"  ✗ Import error: {e}")
    except Exception as e:
        print(f"  ✗ Error: {e}")


if __name__ == "__main__":
    asyncio.run(main())
