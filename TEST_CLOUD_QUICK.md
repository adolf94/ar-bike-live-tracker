# Quick Cloud Messaging Testing Guide

## 1. Enable Cloud Messaging
Edit `backend/local.settings.json` and set:
```json
"ENABLE_CLOUD_MESSAGING": "true",
"AUTOMATE_ENABLED": "true",
"FCM_ENABLED": "true"
```

## 2. Configure Automate (Optional)
For Automate testing, you need:
1. Get Automate secret from https://llamalab.com/automate/cloud/
2. Add to `local.settings.json`:
```json
"AUTOMATE_SECRET": "your_secret_here",
"AUTOMATE_TO": "your.email@gmail.com"
```

## 3. Configure FCM (Optional)
For FCM testing, you need:
1. Create Firebase project
2. Download service account JSON
3. Add to `local.settings.json`:
```json
"FCM_PROJECT_ID": "your-project-id",
"FCM_SERVICE_ACCOUNT_JSON": "path/to/service-account.json"
```

## 4. Testing Commands

### A) Broadcast Test Only (No Cloud)
```bash
python broadcast_test.py --event unauthorized_movement --speed x25 --ignition false
```

### B) Show Cloud Configuration (Lightweight)
```bash
python broadcast_test.py --show-cloud-config
```

### C) Broadcast + Cloud Test
```bash
# Test both broadcast and cloud messaging
python broadcast_test.py --event unauthorized_movement --speed 25 --ignition false --test-cloud
```

### D) Dedicated Cloud Testing (No Database)
```bash
# Test Automate only
python cloud_test_cli.py --event unauthorized_movement --automate

# Test FCM with token
python cloud_test_cli.py --event conn_lost --fcm --fcm-token YOUR_FCM_TOKEN

# Test both
python cloud_test_cli.py --event unauthorized_movement --automate --fcm --fcm-token YOUR_FCM_TOKEN
```

## 5. Event Types Available
.
unauthorized_movement (High Priority)
.
conn_lost (High Priority)
.
conn_restore (Normal Priority)
.
movement_started (Normal Priority)
.
movement_stopped (Normal Priority)
.
engine_off (Normal Priority)

## 6. Quick Start (Minimal Configuration)

If you just want to test the code without actual cloud services:

1. Enable cloud messaging but leave providers disabled:
```json
"ENABLE_CLOUD_MESSAGING": "true",
"AUTOMATE_ENABLED": "false",
"FCM_ENABLED": "false"
```

2. Run tests to see configuration:
```bash
python broadcast_test.py --show-cloud-config
```

3. You'll see which providers need configuration.

## 7. Expected Output

### With --test-cloud flag:
```
Broadcasting event 'unauthorized_movement' to hub 'telemetry_hub'...
Broadcast finished!

==================================================
TESTING CLOUD MESSAGING
==================================================
Event: unauthorized_movement
Speed: 25.0 km/h
Ignition: false
Location: 14.55043, 121.07967

=== Testing Providers ===

Automate:
  ✗ Not configured (missing AUTOMATE_SECRET or AUTOMATE_TO)

FCM:
  ⓘ FCM testing requires database connection
  Use cloud_test_cli.py --fcm --fcm-token YOUR_TOKEN for FCM testing
```

This shows you exactly what needs to be configured to get cloud messaging working.