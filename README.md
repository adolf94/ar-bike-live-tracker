"# Antigravity - Real-time Vehicle Telemetry System

A serverless, real-time telemetry monitoring system for Honda PCX 160 vehicles that polls the AIKA REST API, persists historical data in Azure Cosmos DB, and broadcasts movement events to frontend clients via WebSockets.

## Features

- **Real-time Telemetry Polling**: Fetches vehicle data every 20 seconds from AIKA API
- **Event Detection**: Detects movement start/stop, unauthorized movement, and engine status changes
- **WebSocket Broadcasting**: Real-time updates to connected frontend clients using Azure Web PubSub
- **Historical Data Storage**: Persists all telemetry data in Azure Cosmos DB for analytics
- **Interactive Dashboard**: React-based frontend with live map, status grid, and event logging
- **Android Notifications**: Push notifications via LlamaLabs Automate for critical events
- **Device Control**: Send commands to vehicle (engine on/off, lock/unlock)
- **Authentication**: OIDC-based authentication via custom identity provider

## Architecture

```
┌─────────────┐    ┌─────────────┐    ┌─────────────┐
│   Frontend  │◄───│  WebSocket  │◄───│   Backend   │
│  (React)    │    │   Clients   │    │(Azure Func) │
└─────────────┘    └─────────────┘    └─────────────┘
                            │                   │
                    HTTP Fallback           Timer Trigger
                            │                   │
┌─────────────┐    ┌─────────────┐    ┌─────────────┐
│  Android    │    │    AIKA     │    │   Cosmos    │
│  Notify     │◄───│    API      │◄───│     DB      │
│ (Automate)  │    │             │    │             │
└─────────────┘    └─────────────┘    └─────────────┘
```

## Tech Stack

### Backend (Azure Functions - Python)
- **Runtime**: Azure Functions v2 (Python 3.9+)
- **Database**: Azure Cosmos DB (Serverless)
- **Real-time**: Azure Web PubSub
- **Authentication**: OIDC with custom identity provider
- **Monitoring**: Application Insights

### Frontend (React + TypeScript)
- **Framework**: React 19 with TypeScript
- **Build Tool**: Vite
- **Mapping**: Leaflet + React Leaflet
- **Styling**: Tailwind CSS
- **Icons**: Lucide React
- **PWA**: Vite PWA plugin

## Getting Started

### Prerequisites
- Node.js 18+ and npm
- Python 3.9+
- Azure Functions Core Tools
- Azure CLI
- Cosmos DB Emulator (for local development)

### Backend Setup
```bash
cd backend
python -m venv venv
.\venv\Scripts\activate
pip install -r requirements.txt
```

### Frontend Setup
```bash
cd frontend
npm install
npm run dev
```

### Environment Configuration
1. Copy `backend/local.settings.example.json` to `backend/local.settings.json`
2. Copy `frontend/public/appconfig.example.js` to `frontend/public/appconfig.js`
3. Configure API endpoints, authentication, and Azure service credentials

## Deployment

### Backend to Azure Functions
```bash
cd backend
func azure functionapp publish <function-app-name>
```

### Frontend to Azure Static Web Apps
```bash
cd frontend
npm run build
```

### CI/CD
GitHub Actions workflows are configured in `.github/workflows/`:
- `master_bike-tracker-api.yml`: Backend deployment
- `master_bike-tracker-web.yml`: Frontend deployment

## API Endpoints

### Telemetry Polling
- `GET /api/telemetry`: Get current telemetry state
- `GET /api/telemetry/history`: Get historical telemetry data

### Event Subscription
- WebSocket connection to Azure Web PubSub for real-time events

### Device Control
- `POST /api/control/engine`: Start/stop engine
- `POST /api/control/lock`: Lock/unlock vehicle
- `POST /api/control/honk`: Honk horn

## Event Types

- `movement_started`: Vehicle begins moving
- `movement_stopped`: Vehicle comes to a stop
- `unauthorized_movement`: Movement detected while engine is off
- `engine_off`: Engine turned off
- `engine_on`: Engine turned on
- `location_update`: Significant location change

## Cost Optimization

- **Azure Functions**: Consumption plan (free tier up to 1M executions/month)
- **Cosmos DB**: Serverless tier (pay per request)
- **Web PubSub**: Free tier (20k messages/day, 20 connections)
- **Estimated Monthly Cost**: < $1.00

## Development Notes

- Event detection uses state comparison to minimize false positives
- Fallback to HTTP polling when WebSockets disconnect
- Token-based authentication with automatic refresh
- Comprehensive logging and error handling

## Related Documentation

- [System Specification](./spec.md)
- [Android Notification Integration](./automate_plan.md)
- [Testing Utilities](./broadcast_test.py)" 
