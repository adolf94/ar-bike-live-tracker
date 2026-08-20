# Cloud Messaging Testing Guide (Simplified)

## Overview
Two separate scripts for different purposes:

1. **`broadcast_test.py`** - Simple broadcast testing only
2. **`test_cloud_messaging_cli.py`** - Dedicated cloud messaging testing

## Quick Start

### Simple Broadcast Testing Only
```bash
# Broadcast a movement_started event
python broadcast_test.py --event movement_started

# Broadcast unauthorized movement
python broadcast_test.py --event unauthorized_movement --speed 25 --ignition false

# Show cloud messaging configuration (lightweight, no DB connections)
python broadcast_test.py --show-cloud-config
```

### Dedicated Cloud Messaging Testing
```bash
# Quick configuration check
python test_cloud_messaging_cli.py --quick

# Show full configuration
python test_cloud_messaging_cli.py --config-only

# Send unauthorized movement notification
python test_cloud_messaging_cli.py --event unauthorized_movement

# Send connection lost notification
python test_cloud_messaging_cli.py --event conn_lost

# List all available event types
python test_cloud_messaging_cli.py --list-events
```

## Script Comparison

| Feature | `broadcast_test.py` | `test_cloud_messaging_cli.py` |
|---------|-------------------|-----------------------------|
| Broadcast testing | ✅ Yes | ❌ No |
| Cloud messaging testing | ❌ Config only | ✅ Full testing |
| Database connections | ❌ None | ✅ Required for FCM |
| Dependencies | Minimal | Full cloud messaging stack |
| Use case | Quick broadcast tests | End-to-end cloud messaging tests |

## Configuration

### Enable Cloud Messaging
Edit `backend/local.settings.json`:
```json
"ENABLE_CLOUD_MESSAGING": "true",
"AUTOMATE_ENABLED": "true",
"FCM_ENABLED": "true"
```

### Event Types

| Event | Description | Default Priority |
|-------|-------------|------------------|
| `unauthorized_movement` | Vehicle moving with ignition off | High |
| `conn_lost` | Device connection lost | High |
| `conn_restore` | Device connection restored | Normal |
| `movement_started` | Vehicle starts moving | Normal |
| `movement_stopped` | Vehicle stops moving | Normal |
| `engine_off` | Engine turned off | Normal |

## Examples

### Example 1: Simple Broadcast
```bash
# Broadcast movement started event
python broadcast_test.py --event movement_started --speed 45 --ignition true

# Output:
# Broadcasting event 'movement_started' (speed: 45.0 km/h, ignition: true) to hub 'telemetry_hub'...
# Broadcast finished!
```

### Example 2: Cloud Messaging Configuration Check
```bash
# Lightweight config check (no DB connections)
python broadcast_test.py --show-cloud-config

# Output shows:
# - If cloud messaging is enabled
# - Automate configuration status
# - FCM configuration status
# - Event filtering settings
```

### Example 3: Full Cloud Messaging Test
```bash
# Test cloud messaging with unauthorized movement
python test_cloud_messaging_cli.py --event unauthorized_movement

# Output shows:
# - Configuration check
# - Provider initialization
# - Notification sending attempt
# - Success/failure results
```

## Troubleshooting

### broadcast_test.py fails
**Error**: Import errors or missing dependencies
**Solution**: Make sure you're in the project root and dependencies are installed:
```bash
pip install -r backend/requirements.txt
```

### test_cloud_messaging_cli.py fails
**Error**: Database connection errors
**Solution**: This is expected if CosmosDB isn't configured. FCM requires database for token management.

### No Cloud Messaging Providers Enabled
```
⚠ No cloud messaging providers are enabled!
```
**Solution**: Configure at least one provider in `local.settings.json`.

### Configuration Syntax Errors
**Solution**: Check JSON syntax in `backend/local.settings.json`.

## Best Practices

1. **Use `broadcast_test.py` for**: Simple broadcast testing, quick config checks
2. **Use `test_cloud_messaging_cli.py` for**: Full cloud messaging testing, provider verification
3. **For development**: Start with broadcast_test.py, move to cloud messaging when ready
4. **For production testing**: Use test_cloud_messaging_cli.py with real credentials

## File Structure

```
obd2_polling_notifier/
├── broadcast_test.py              # Simple broadcast testing (87 lines)
├── test_cloud_messaging_cli.py    # Dedicated cloud messaging testing
├── CLOUD_MESSAGING_TESTING.md     # This guide
└── backend/
    ├── local.settings.json        # Configuration
    └── services/                  # Cloud messaging implementation
```

Both scripts are now simplified and focused on their specific purposes, with minimal dependencies and clear separation of concerns.