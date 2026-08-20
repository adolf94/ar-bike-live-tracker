#!/usr/bin/env python3
"""
Quick import test for cloud messaging feature.
"""

import sys
import os
from pathlib import Path

# Add backend directory to path
backend_dir = Path(__file__).parent
sys.path.insert(0, str(backend_dir))

print("Testing imports...")

try:
    # Test basic imports
    from models.telemetry import EventType
    print("✓ models.telemetry imported")
    
    from models.documents import TelemetryDocument, DeviceTokenDocument
    print("✓ models.documents imported")
    
    from services.cloud_messaging_service import CloudMessagingService, MessagePriority
    print("✓ services.cloud_messaging_service imported")
    
    from services.automate_service import AutomateService
    print("✓ services.automate_service imported")
    
    from services.fcm_service import FcmService
    print("✓ services.fcm_service imported")
    
    from services.cosmos_service import CosmosService
    print("✓ services.cosmos_service imported")
    
    print("\n✓ All imports successful!")
    
except ImportError as e:
    print(f"\n✗ Import error: {e}")
    print(f"File: {e.__traceback__.tb_frame.f_code.co_filename if hasattr(e, '__traceback__') else 'unknown'}")
    import traceback
    traceback.print_exc()
    sys.exit(1)

except Exception as e:
    print(f"\n✗ Error: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)