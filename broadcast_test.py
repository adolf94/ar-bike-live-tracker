import argparse
import asyncio
import json
import os
import sys

# Ensure backend directory is in python path to import services/models correctly
sys.path.append(os.path.join(os.path.dirname(__file__), 'backend'))

from services.broadcast_service import BroadcastService

async def main():
    parser = argparse.ArgumentParser(description="Broadcast simulated telemetry events to Web PubSub / SignalR.")
    parser.add_argument("-e", "--event", type=str, default="movement_started",
                        help="Event name to trigger (e.g. movement_started, overspeed_alert, sos_alert, ignition_on, ignition_off)")
    parser.add_argument("-s", "--speed", type=float, default=45.0, help="Simulated speed (km/h)")
    parser.add_argument("--lat", type=float, default=14.55043, help="Simulated latitude")
    parser.add_argument("--lng", type=float, default=121.07967, help="Simulated longitude")
    parser.add_argument("-i", "--ignition", type=str, default="true", choices=["true", "false"],
                        help="Ignition state (true or false)")
    
    args = parser.parse_args()
    
    # Try loading from any .env files in the workspace (root, backend, frontend)
    envs = {}
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
                            envs[k.strip()] = v.strip().strip('"').strip("'")
            except Exception as err:
                print(f"Warning: Could not parse {path}: {err}")

    conn_str = envs.get("WebPubSubConnectionString") or envs.get("WEBPUBSUB_CONNECTION_STRING") or envs.get("WEBPUBSUB_CONN")

    if not conn_str:
        # Fall back to local.settings.json if not found in .env files
        settings_path = os.path.join(os.path.dirname(__file__), "backend", "local.settings.json")
        if os.path.exists(settings_path):
            try:
                with open(settings_path, "r") as f:
                    settings = json.load(f)
                    conn_str = settings.get("Values", {}).get("WebPubSubConnectionString")
            except Exception as err:
                print(f"Warning: Could not parse local.settings.json: {err}")

    # Final fallback to default emulator connection string
    if not conn_str:
        conn_str = "Endpoint=http://localhost;Port=8888;AccessKey=ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789ABCDEFGH;Version=1.0;"

    hub_name = "telemetry_hub"
    svc = BroadcastService(conn_str, hub_name)
    
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

if __name__ == "__main__":
    asyncio.run(main())
