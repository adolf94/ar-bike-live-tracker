# Integration of LlamaLabs Automate Webhooks for Android Event Notifications

This plan details how to trigger real-time push notifications on an Android phone using LlamaLabs Automate when vehicle telemetry events are detected by the backend.

## User Review Required

> [!IMPORTANT]
> To configure and run this integration, you will need to obtain API credentials from LlamaLabs:
> 1. Visit [https://llamalab.com/automate/cloud/](https://llamalab.com/automate/cloud/).
> 2. Log in with the Google Account registered to the Automate app on your Android phone.
> 3. Click the refresh icon under **Secret** to generate your API secret key.
> 4. Keep this secret key secure. It will be added to your backend settings as `AUTOMATE_SECRET`.

> [!TIP]
> We recommend using dynamic messaging priority:
> - **High Priority** for critical security events like `unauthorized_movement` (to wake up the device and notify you immediately).
> - **Normal Priority** for standard status events like `movement_stopped` or `engine_off` (to conserve battery life on your phone).

## Open Questions

> [!WARNING]
> Please review and confirm the following design decisions:
> - Should we send notification messages for **all** events (`movement_started`, `movement_stopped`, `unauthorized_movement`, `engine_off`), or only critical security alerts (`unauthorized_movement` and `movement_started`)? The current proposal enables all events but makes them filterable/configurable.
> - Do you want the webhook payload to contain raw coordinates and speed so you can use them directly in the Automate flow (e.g., to launch Google Maps on your phone or display the speed)?

## Proposed Changes

### Backend Components

---

#### [NEW] [automate_service.py](file:///d:/Users/adolf/source/repos/obd2_polling_notifier/backend/services/automate_service.py)

Create a service to interact with the Automate Cloud Messaging API.

- Endpoint: `https://llamalab.com/automate/cloud/message`
- Method: `POST` (JSON payload)
- Payload Schema:
  ```json
  {
    "secret": "<AUTOMATE_SECRET>",
    "to": "<AUTOMATE_TO>",
    "device": "<AUTOMATE_DEVICE>",
    "priority": "normal" | "high",
    "payload": {
      "event": "unauthorized_movement" | "movement_started" | "movement_stopped" | "engine_off",
      "deviceId": "string",
      "timestamp": "ISO-8601",
      "speed": float,
      "lat": float,
      "lng": float,
      "batteryLevel": int,
      "isOnline": bool
    }
  }
  ```

---

#### [MODIFY] [function_app.py](file:///d:/Users/adolf/source/repos/obd2_polling_notifier/backend/function_app.py)

Update the timer-triggered function to forward events to the LlamaLabs Automate service:
1. Retrieve environment variables:
   - `AUTOMATE_SECRET`: Secret token generated from LlamaLabs cloud portal.
   - `AUTOMATE_TO`: Google account email address.
   - `AUTOMATE_DEVICE`: (Optional) Target device brand/model (e.g., "Google Pixel 8").
   - `AUTOMATE_ENABLED`: Boolean switch (`true`/`false`).
2. Lazy-initialize `_automate_svc` if credentials are provided.
3. In `poll_telemetry` function, if an `event` is triggered and `AUTOMATE_ENABLED` is true, call `_automate_svc.send_event_notification(...)`.

---

#### [MODIFY] [local.settings.json](file:///d:/Users/adolf/source/repos/obd2_polling_notifier/backend/local.settings.json)

Add local settings fields for local testing.

```json
"AUTOMATE_ENABLED": "true",
"AUTOMATE_SECRET": "YOUR_AUTOMATE_SECRET_HERE",
"AUTOMATE_TO": "your.email@gmail.com",
"AUTOMATE_DEVICE": ""
```

---

## Suggested Automate Flow Design on Android

To receive and handle these events on your Android phone, set up a flow in the **Automate** app with the following blocks. This setup creates an "alarm-like" experience for critical events that loops until you acknowledge it.

1. **Cloud Message Receive Block**:
   - **Account**: Select your Google Account.
   - **Payload**: Define a variable name to store the received payload (e.g., `event_data`).
2. **Expression True Block**:
   - **Formula**: `event_data.event = "unauthorized_movement"` (checks if the event is a critical security alert).
   - **YES path** goes to step 3 (High-Priority Alarm Flow).
   - **NO path** goes to standard notification blocks (e.g., a simple `Notification show` block).

**High-Priority Alarm Flow (YES Path):**
3. **Device Keep Awake Block**:
   - **Action**: `Wake up` (Turns on the screen when the alert arrives).
4. **Audio Volume Set Block**:
   - **Audio stream**: `Alarm`
   - **Volume**: `100%` (Ensures you hear it).
5. **Sound Play Block**:
   - **Audio stream**: `Alarm`
   - **Sound URI**: Choose a loud/distinct alarm sound.
   - **Loop sound**: ☑ Checked (Keep ringing like a call).
   - **Proceed**: `Immediately` (Crucial: lets the flow show the notification while ringing).
6. **Notification Channel Block**:
   - **Channel ID**: `"critical_alarms"`
   - **Name**: `"Critical Vehicle Alarms"`
   - **Importance**: `Urgent` (Forces a popup over the screen).
   - **Visibility**: `Public` (Shows on lock screen).
   - **Bypass DND**: ☑ Checked.
7. **Notification Show Block**:
   - **Channel ID**: `"critical_alarms"` (Must match step 6).
   - **Title**: `"🚨 UNAUTHORIZED MOVEMENT 🚨"`
   - **Message**: `"Speed: " ++ event_data.speed ++ " km/h. Location: " ++ event_data.lat ++ ", " ++ event_data.lng`
   - **Action 1**: `"Stop Alarm"`
   - **Proceed**: `When interacted` (Pauses the flow here until you tap the notification).
8. **Sound Stop Block**:
   - Stops the looping alarm sound after you interact with the notification.

---

## Verification Plan

### Automated Tests
We will add a new test file:
- `backend/tests/test_automate_service.py` to verify formatting, error handling, and mock requests to the LlamaLabs endpoint.

### Manual Verification
1. We will create a local script `backend/send_test_notification.py` that allows testing of the webhook notification directly to your phone.
2. You can trigger this script locally to verify that your Android phone receives the notification with correct fields before deploying the function app.
