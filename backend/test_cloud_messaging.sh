#!/usr/bin/env bash
# Test script for cloud messaging configuration

echo "=== Cloud Messaging Configuration Test ==="
echo ""

# Check if we're in the right directory
if [ ! -f "local.settings.json" ]; then
    echo "Error: Must run from backend directory"
    echo "cd backend && ./test_cloud_messaging.sh"
    exit 1
fi

# Check Python environment
echo "Checking Python environment..."
python --version
if [ $? -ne 0 ]; then
    echo "Error: Python not found"
    exit 1
fi

# Install required packages if needed
echo ""
echo "Checking dependencies..."
pip install -q httpx azure-cosmos azure-identity > /dev/null 2>&1
if [ $? -ne 0 ]; then
    echo "Warning: Some dependencies may not be installed"
fi

# Run the test
echo ""
echo "Running configuration test..."
python test_cloud_messaging.py

echo ""
echo "=== Environment Configuration Summary ==="
echo ""

# Display current configuration
echo "Current cloud messaging configuration:"
echo "ENABLE_CLOUD_MESSAGING: $(grep -o '"ENABLE_CLOUD_MESSAGING": "[^"]*"' local.settings.json | cut -d'"' -f4)"
echo "AUTOMATE_ENABLED: $(grep -o '"AUTOMATE_ENABLED": "[^"]*"' local.settings.json | cut -d'"' -f4)"
echo "FCM_ENABLED: $(grep -o '"FCM_ENABLED": "[^"]*"' local.settings.json | cut -d'"' -f4)"
echo ""

echo "Event filtering configuration:"
echo "AUTOMATE_ENABLED_EVENTS: $(grep -o '"AUTOMATE_ENABLED_EVENTS": "[^"]*"' local.settings.json | cut -d'"' -f4)"
echo "FCM_ENABLED_EVENTS: $(grep -o '"FCM_ENABLED_EVENTS": "[^"]*"' local.settings.json | cut -d'"' -f4)"
echo ""

echo "To modify configuration:"
echo "1. Edit local.settings.json"
echo "2. Set ENABLE_CLOUD_MESSAGING=true to enable"
echo "3. Set AUTOMATE_ENABLED=true/false for Automate"
echo "4. Set FCM_ENABLED=true/false for FCM"
echo "5. Configure AUTOMATE_SECRET and AUTOMATE_TO for Automate"
echo "6. Configure FCM_PROJECT_ID and FCM_SERVICE_ACCOUNT_JSON for FCM"
echo ""