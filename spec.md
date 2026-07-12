# Antigravity: Telemetry & Event Middleware Specification

## 1. System Overview
**Project Name:** Antigravity  
**Objective:** A serverless, highly-available middleware layer designed to poll the AIKA REST API for vehicle telemetry (specifically for the Honda PCX 160), persist historical data, and broadcast real-time movement events to frontend clients via WebSockets.  
**Core Strategy:** Utilize a fully decoupled, serverless architecture to avoid long-running compute costs, relying on state-comparison logic to infer real-time events.

---

## 2. Architecture & Components

The system relies on three core Azure services to maintain a near-zero cost profile while ensuring real-time responsiveness.

### 2.1 The Poller: Azure Functions (Consumption Plan)
*   **Trigger:** Timer Trigger (`*/10 * * * * *` - executes every 10 seconds).
*   **Responsibility:**
    1. Authenticates and fetches current telemetry from the AIKA API.
    2. Retrieves the *previous* state from Cosmos DB.
    3. Computes state deltas (e.g., speed changes, ignition toggles).
    4. Evaluates event triggers (`movement_started`, `movement_stopped`).
    5. Saves the *new* state to Cosmos DB.
    6. Dispatches events to Azure Web PubSub if conditions are met.
*   **Language Stack:** Python or C# (.NET).

### 2.2 The State Engine: Azure Cosmos DB (Serverless Tier)
*   **Responsibility:** Acts as the system of record for all telemetry pings and holds the immediate past state required for event computation.
*   **Partition Key:** `/deviceId`
*   **TTL (Time-To-Live):** Configurable. Recent state documents can be kept indefinitely, or a TTL can be applied to raw pings (e.g., 30 days) to minimize storage costs, while aggregating daily trip summaries.

### 2.3 The Broadcaster: Azure Web PubSub (Free Tier)
*   **Responsibility:** Maintains persistent WebSocket connections with frontend clients (e.g., web dashboards).
*   **Integration:** The Azure Function uses the Web PubSub output binding or SDK to publish JSON payloads to a specific `hub` (e.g., `telemetry_hub`).

---

## 3. Cosmos DB Data Schema

Documents stored in Cosmos DB will follow this structure to optimize for both point-in-time state checks and historical route mapping.

```json
{
  "id": "uuid-v4",
  "deviceId": "string",
  "timestamp": "2026-07-11T23:22:55Z",
  "location": {
    "lat": 14.5794,
    "lng": 121.0594,
    "course": 180
  },
  "status": {
    "speed": 12.5,
    "isIgnitionOn": true,
    "batteryLevel": 98,
    "isOnline": true
  },
  "eventTriggered": "movement_started" // null if just a routine poll
}
```

---

## 4. Event Engineering Logic

To mitigate GPS drift and false positives, the system uses composite logic to determine if an event should be broadcasted to the WebSocket clients.

### 4.1 Movement Started
Triggered when the vehicle transitions from a parked state to an active state.
*   **Condition A (Speed):** Current `speed` > 5 km/h AND Previous `speed` <= 5 km/h.
*   **Condition B (Ignition):** Current `isIgnitionOn` == true AND Previous `isIgnitionOn` == false.
*   *Action:* Broadcast `movement_started` event payload to Web PubSub.

### 4.2 Movement Stopped
Triggered when the vehicle comes to a complete halt after a period of movement.
*   **Condition:** Current `speed` == 0 AND Previous `speed` > 0.
*   *Action:* Broadcast `movement_stopped` event payload to Web PubSub.

### 4.3 Security Alert (Optional)
Triggered when unauthorized movement is detected.
*   **Condition:** Current `speed` > 5 km/h AND Current `isIgnitionOn` == false.
*   *Action:* Broadcast high-priority `unauthorized_movement` event.

---

## 5. Sequence Diagram Flow

1. **Timer** fires every 10s -> wakes up **Azure Function**.
2. **Function** calls AIKA API -> receives `CurrentState`.
3. **Function** queries **Cosmos DB** for `Top 1` document where `deviceId = X` `ORDER BY timestamp DESC` -> receives `PreviousState`.
4. **Function** compares `CurrentState` vs `PreviousState`.
5. **Function** writes `CurrentState` to **Cosmos DB**.
6. *If event condition met:* **Function** sends HTTP POST to **Azure Web PubSub**.
7. **Web PubSub** pushes payload to connected WebSocket clients.
8. **Function** shuts down.

---

## 6. Cost Projection (Monthly)

*   **Azure Functions (Consumption):** ~260k executions/mo. (Well within the 1 million free grant). **$0.00**
*   **Azure Cosmos DB (Serverless):** Minimal read/write RUs for 260k operations. **~$0.50 - $1.00**
*   **Azure Web PubSub (Free Tier):** Limit 20k messages/day, 20 concurrent connections. **$0.00**
*   **Total Estimated Cost:** **<$1.00 / month**
