# Antigravity: Real-time Vehicle Telemetry System Specification

## 1. System Overview

**Project Name:** Antigravity (BikeTracker)  
**Objective:** A serverless, highly-available middleware layer designed to poll the AIKA REST API for vehicle telemetry (specifically for the Honda PCX 160), persist historical data, broadcast real-time movement events to frontend clients via WebSockets, and trigger push notifications on Android devices.

**Core Architecture:** Fully decoupled serverless architecture using Azure Functions for compute, Azure Cosmos DB for state management, and Azure Web PubSub for real-time communication. Event detection is based on state-comparison logic with comprehensive telemetry monitoring.

**Estimated Monthly Cost:** < $1.00

---

## 2. System Architecture & Components

### 2.1 Core Services

#### Azure Functions (Consumption Plan)
- **Polling Trigger:** Timer trigger executing every 20 seconds (`*/20 * * * * *`)
- **Primary Responsibilities:**
  1. Authenticate with AIKA API using OAuth2 token
  2. Fetch current telemetry state from vehicle
  3. Retrieve previous state from Cosmos DB
  4. Compute state deltas and detect events
  5. Persist new state to Cosmos DB
  6. Broadcast events to connected WebSocket clients
  7. Trigger Android push notifications for critical events

#### Azure Cosmos DB (Serverless Tier)
- **Purpose:** System of record for all telemetry data and historical state
- **Partition Key:** `/deviceId`
- **TTL Strategy:** Raw telemetry pings retained for 30 days with daily aggregation
- **Query Patterns:** Latest state retrieval, historical analysis, trip reconstruction

#### Azure Web PubSub (Free Tier)
- **Role:** Real-time message broadcasting to frontend clients
- **Capacity:** 20,000 messages/day, 20 concurrent connections
- **Integration:** WebSocket connections with automatic reconnection and fallback

#### Azure Static Web Apps
- **Frontend Hosting:** React-based dashboard with PWA capabilities
- **Configuration:** Environment-specific app configuration

### 2.2 Additional Components

#### AIKA REST API Integration
- **Protocol:** HTTP REST with OAuth2 authentication
- **Polling Frequency:** 20-second intervals
- **Data Points:** GPS location, speed, ignition status, battery level, online status

#### Authentication Service (auth.adolfrey.com)
- **Protocol:** OIDC/OAuth2 custom identity provider
- **Tokens:** JWT-based access and refresh tokens
- **Integration:** Frontend authentication flow with automatic token management

#### LlamaLabs Automate Integration
- **Purpose:** Android push notifications for critical events
- **Trigger:** HTTP webhook calls from Azure Function
- **Events:** Unauthorized movement, movement start/stop alerts

---

## — CONTINUED BELOW —

## 3. Data Models & Schema

### 3.1 Cosmos DB Document Schema

Documents stored in Cosmos DB follow a structured format optimized for state comparison and historical analysis:

```json
{
  "id": "uuid-v4",
  "deviceId": "honda-pcx-160",
  "timestamp": "2026-07-11T23:22:55Z",
  "location": {
    "lat": 14.5794,
    "lng": 121.0594,
    "course": 180,
    "accuracy": 15.0
  },
  "status": {
    "speed": 12.5,
    "isIgnitionOn": true,
    "batteryLevel": 98,
    "isOnline": true,
    "gpsFix": true,
    "gsmSignal": 85,
    "charging": false,
    "distance": 1250.75
  },
  "eventTriggered": "movement_started",
  "deviceTime": "2026-07-11T23:22:55Z",
  "metadata": {
    "pollInterval": 20,
    "apiVersion": "2.0",
    "deviceModel": "Honda PCX 160"
  }
}
```

### 3.2 Event Payload Schema

Events broadcast via Web PubSub follow this structure:

```json
{
  "event": "movement_started",
  "timestamp": "2026-07-11T23:22:55Z",
  "deviceId": "honda-pcx-160",
  "location": {
    "lat": 14.5794,
    "lng": 121.0594
  },
  "status": {
    "speed":12.5,
    "isIgnitionOn": true,
    "batteryLevel": 98
  },
  "previousState": {
    "speed": 0.0,
    "isIgnitionOn": false
  }
}
```

### 3.3 Telemetry State Model (Python)

```python
class TelemetryState:
    id: str  # UUID
    device_id: str
    timestamp: datetime
    location: Location
    status: VehicleStatus
    event_triggered: Optional[str] = None
    device_time: Optional[datetime] = None
    metadata: Dict[str, Any] = None
```

---

## 4. Event Detection Logic

Event detection uses composite logic combining multiple telemetry parameters to minimize false positives from GPS drift or sensor noise.

### 4.1 Core Event Types

#### Movement Started
**Trigger:** Vehicle transitions from parked to active state
- **Speed Condition:** Current `speed` > 5 km/h AND Previous `speed` ≤ 5 km/h
- **Ignition Condition:** Current `isIgnitionOn` == true AND Previous `isIgnitionOn` == false
- **Location Change:** Significant GPS coordinate change (> 50m radius)
- **Action:** Broadcast `movement_started` event, trigger Android notification

#### Movement Stopped
**Trigger:** Vehicle comes to complete halt after movement period
- **Speed Condition:** Current `speed` == 0 AND Previous `speed` > 5 km/h
- **Duration Condition:** Speed == 0 for ≥ 30 seconds (to filter temporary stops)
- **Action:** Broadcast `movement_stopped` event

#### Unauthorized Movement
**Trigger:** Vehicle movement detected while engine is off (security alert)
- **Speed Condition:** Current `speed` > 5 km/h
- **Ignition Condition:** Current `isIgnitionOn` == false
- **Action:** High-priority `unauthorized_movement` event with immediate Android notification

#### Engine State Changes
**Engine Off:**
- Current `isIgnitionOn` == false AND Previous `isIgnitionOn` == true
- Broadcast `engine_off` event

**Engine On:**
- Current `isIgnitionOn` == true AND Previous `isIgnitionOn` == false
- Broadcast `engine_on` event

#### Location Update
**Trigger:** Significant location change without other state changes
- **Distance Condition:** Haversine distance > 100 meters
- **Speed Filter:** Speed < 2 km/h (to distinguish from movement)
- **Action:** `location_update` event for map tracking

### 4.2 Event Suppression Logic
- **Debouncing:** Minimum 60 seconds between same event type
- **GPS Filtering:** Ignore events when GPS accuracy > 50 meters
- **Signal Filtering:** Ignore events when GSM signal < 20%

---

## — CONTINUED BELOW —

## 5. System Sequence Flow

### 5.1 Main Polling Cycle (20-second interval)

1. **Timer Trigger** → Azure Function wakes up (Consumption plan)
2. **Authentication** → Refresh OAuth2 token if expired
3. **API Call** → Fetch current telemetry from AIKA REST API
4. **State Retrieval** → Query Cosmos DB: `SELECT TOP 1 * FROM c WHERE c.deviceId = @deviceId ORDER BY c.timestamp DESC`
5. **Event Detection** → Compare current vs. previous state using Event Engine
6. **Data Persistence** → Write new telemetry document to Cosmos DB
7. **Event Broadcasting** → If event detected:
   - Send to Azure Web PubSub hub
   - Trigger Android notification via LlamaLabs Automate webhook
8. **Cleanup** → Function completes execution, resources released

### 5.2 Real-time Client Communication

```
Frontend Client → WebSocket Connection → Azure Web PubSub
        ↑                                       ↓
HTTP Polling Fallback ← Connection Loss ← Broadcast Events
```

### 5.3 Failure Recovery Scenarios

1. **AIKA API Unavailable** → Log error, skip cycle, retry next interval
2. **Cosmos DB Unavailable** → Cache state in memory, retry with backoff
3. **Web PubSub Failure** → Fallback to HTTP polling for clients
4. **Authentication Failure** → Attempt token refresh, escalate if persistent

---

## 6. Frontend Architecture

### 6.1 React Dashboard Components

#### Map View (`components/Map.tsx`)
- **Library:** Leaflet with React Leaflet bindings
- **Features:** Real-time vehicle marker, historical trail, geofence visualization
- **Updates:** Smooth marker animation between location updates

#### Status Grid (`components/StatusGrid.tsx`)
- **Display:** Current speed, battery, ignition status, GPS signal
- **Updates:** Real-time via WebSocket, color-coded status indicators
- **History:** Sparkline charts for trend visualization

#### Event Log (`components/EventLog.tsx`)
- **Features:** Chronological event display with timestamps
- **Filtering:** Event type filtering, search functionality
- **Notifications:** Toast notifications for new events

#### Control Panel (`components/ControlPanel.tsx`)
- **Functions:** Engine start/stop, vehicle lock/unlock, horn control
- **Security:** PIN confirmation for critical operations
- **Feedback:** Command status and execution confirmation

### 6.2 WebSocket Client Implementation

```typescript
// WebSocket connection with automatic reconnection
const client = new WebPubSubClient({
  getClientAccessUrl: async () => {
    const token = await getAccessToken();
    return `wss://${endpoint}/client/hubs/${hub}?access_token=${token}`;
  }
});

// Event subscription
client.on('connected', () => { /* Handle connection */ });
client.on('message', (event) => { /* Process telemetry events */ });
client.on('disconnected', () => { /* Switch to HTTP polling */ });
```

### 6.3 Authentication Flow

1. **Initial Load** → Redirect to OIDC login page
2. **Authorization Code** → Exchange for access/refresh tokens
3. **Token Management** → Automatic refresh before expiry
4. **Session Persistence** → Local storage with encryption
5. **Logout** → Clear tokens, redirect to login

---

## 7. Deployment & Operations

### 7.1 Infrastructure Configuration

#### Azure Resources
- **Function App:** `bike-tracker-api` (Consumption plan, Python 3.9)
- **Cosmos DB:** `bike-telemetry-db` (Serverless, Core SQL API)
- **Web PubSub:** `bike-wps` (Free tier, Standard SKU)
- **Static Web App:** `bike-tracker-web` (Standard tier)

#### Environment Variables
```bash
# Backend (local.settings.json)
AIKA_API_BASE_URL=https://api.aika.com/v2
AIKA_CLIENT_ID=xxx
AIKA_CLIENT_SECRET=xxx
COSMOS_CONNECTION_STRING=AccountEndpoint=...
WEBPUBSUB_CONNECTION_STRING=Endpoint=...
AUTH_ENDPOINT=https://auth.adolfrey.com

# Frontend (appconfig.js)
window.appConfig = {
  apiBaseUrl: 'https://bike-tracker-api.azurewebsites.net',
  websocketEndpoint: 'wss://bike-wps.webpubsub.azure.com',
  authEndpoint: 'https://auth.adolfrey.com',
  clientId: 'bike-tracker-web'
};
```

### 7.2 CI/CD Pipeline

#### Backend Deployment (.github/workflows/master_bike-tracker-api.yml)
1. **Trigger:** Push to `master` branch
2. **Build:** Python dependencies, package function app
3. **Test:** Run unit tests, linting
4. **Deploy:** Publish to Azure Functions
5. **Validation:** Smoke tests, health check

#### Frontend Deployment (.github/workflows/master_bike-tracker-web.yml)
1. **Trigger:** Push to `master` branch
2. **Build:** TypeScript compilation, Vite bundling
3. **Test:** React component tests
4. **Deploy:** Static files to Azure Static Web Apps
5. **Cache:** Configure CDN caching rules

### 7.3 Monitoring & Alerting

#### Application Insights Integration
- **Metrics:** Function execution time, API latency, event counts
- **Logs:** Structured logging with correlation IDs
- **Alerts:** Failed executions, high latency, authentication failures

#### Health Endpoints
- `GET /api/health` → System health status
- `GET /api/telemetry/latest` → Latest telemetry verification
- `GET /api/events/recent` → Recent events for debugging

---

## 8. Security Considerations

### 8.1 Authentication & Authorization
- **OIDC/OAuth2** with custom identity provider
- **JWT tokens** with short-lived access tokens (1 hour)
- **Refresh tokens** for extended sessions (7 days)
- **Scope-based authorization** for API endpoints

### 8.2 Data Protection
- **Encryption at rest:** Cosmos DB automatic encryption
- **Encryption in transit:** TLS 1.2+ for all communications
- **Token storage:** Encrypted local storage in frontend
- **Secret management:** Azure Key Vault integration

### 8.3 API Security
- **Rate limiting:** 100 requests/minute per client
- **Input validation:** Schema validation for all inputs
- **SQL injection prevention:** Parameterized queries
- **Cross-site scripting:** Content security policies

### 8.4 Device Security
- **PIN protection** for vehicle control commands
- **Command confirmation** via frontend UI
- **Audit logging** of all control operations
- **Timeout enforcement** for pending commands

---

## 9. Cost Optimization Strategy

### 9.1 Azure Functions (Consumption Plan)
- **Free Grant:** 1 million executions/month
- **Execution Time:** Optimized to < 5 seconds per invocation
- **Memory:** 1.5GB configuration balanced with performance
- **Cold Start Mitigation:** Timer trigger reduces impact

### 9.2 Azure Cosmos DB (Serverless)
- **Request Units:** Estimated 100 RU/s average
- **Storage:** 5GB initial, 30-day TTL on raw data
- **Indexing:** Custom index policy for query patterns
- **Partitioning:** `deviceId` partition key for distribution

### 9.3 Azure Web PubSub (Free Tier)
- **Messages:** 20,000/day limit (≈ 1 message every 4 seconds)
- **Connections:** 20 concurrent connections
- **Fallback:** HTTP polling when limits approached

### 9.4 Total Monthly Cost Estimate
| Service | Tier | Estimated Monthly Cost |
|---------|------|------------------------|
| Azure Functions | Consumption | $0.00 (within free grant) |
| Azure Cosmos DB | Serverless | $0.50 - $1.00 |
| Azure Web PubSub | Free | $0.00 |
| Azure Static Web Apps | Standard | $0.00 (within free tier) |
| **Total** | | **<$1.00** |

---

## 10. Future Enhancements

### 10.1 Planned Features
- **Geofencing:** Virtual boundaries with entry/exit alerts
- **Trip Analytics:** Distance traveled, fuel efficiency, route optimization
- **Predictive Maintenance:** Alert patterns based on telemetry trends
- **Multi-vehicle Support:** Fleet management dashboard
- **Offline Mode:** Local storage for connectivity issues

### 10.2 Scalability Considerations
- **Multi-region deployment** for global redundancy
- **Event-driven architecture** with Azure Event Grid
- **Microservices decomposition** for independent scaling
- **Caching strategy** with Azure Redis Cache

### 10.3 Integration Opportunities
- **Smart Home Integration:** IoT hub connectivity
- **Calendar Integration:** Trip scheduling and reminders
- **Weather Integration:** Weather-based route suggestions
- **Social Features:** Trip sharing and community features

---

## 11. Appendix

### 11.1 Project Structure
```
obd2_polling_notifier/
├── backend/                    # Azure Functions Python backend
│   ├── function_app.py        # Main function entry point
│   ├── requirements.txt       # Python dependencies
│   ├── local.settings.json    # Local configuration
│   ├── services/              # Business logic services
│   ├── models/                # Data models
│   ├── interfaces/            # Service abstractions
│   └── tests/                 # Unit tests
├── frontend/                  # React TypeScript frontend
│   ├── src/                   # React source code
│   ├── public/                # Static assets
│   └── package.json           # Node.js dependencies
├── .github/workflows/         # CI/CD pipelines
├── spec.md                    # This specification document
├── README.md                  # Project overview
├── automate_plan.md           # Android notification integration
└── broadcast_test.py         # Testing utility
```

### 11.2 Key Technical Decisions
1. **Python for Backend:** Rapid development, strong Azure SDK support
2. **React for Frontend:** Component reusability, strong ecosystem
3. **Serverless Architecture:** Cost optimization, automatic scaling
4. **State Comparison:** Event detection vs. continuous polling
5. **WebSocket with HTTP Fallback:** Balance reliability with real-time needs

### 11.3 Testing Strategy
- **Unit Tests:** Business logic, event detection algorithms
- **Integration Tests:** API endpoints, database operations
- **End-to-End Tests:** Complete user workflows
- **Load Testing:** Concurrent WebSocket connections
- **Security Testing:** Authentication flows, input validation

---

*Last Updated: July 16, 2026*
*Version: 2.0*
