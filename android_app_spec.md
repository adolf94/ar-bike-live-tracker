# Specification: Dedicated Android Companion App & Backend FCM Integration

This specification details the architecture, backend changes, and native Android implementation required to deliver a true, full-screen incoming call/alarm style experience when critical vehicle events (such as `unauthorized_movement`) are triggered.

---

## 1. Overview

To overcome the lock-screen limitations of 3rd-party automation apps, this project will implement a dedicated native Android application built in Kotlin and Jetpack Compose. This app will:
1. Receive high-priority push notifications instantly via Firebase Cloud Messaging (FCM), even if the app is killed or the phone is in deep sleep.
2. Utilize native Android "Full-Screen Intents" to bypass the lock screen, wake the display, and present a persistent, loud alarm UI that loops until manually dismissed.
3. Provide a lightweight, secure status dashboard to check current telemetry without full browser-based dashboard weight.

---

## 2. User Review & Configuration Required

To establish the required infrastructure, you must configure the following accounts and settings:

### A. Firebase & Google Cloud Setup
1. Go to the [Firebase Console](https://console.firebase.google.com/).
2. Create a new project (e.g., `Antigravity Tracker`).
3. Add an Android app to the project. Use package name `com.adolfrey.biketracker`.
4. Download the generated `google-services.json` and place it in the Android app's `app/` directory.
5. In the Firebase Console, go to **Project Settings > Service Accounts**.
6. Click **Generate New Private Key** to download the JSON credentials file for the Firebase Admin SDK.
7. Keep this JSON secure; it will be used by the Python backend as `FCM_SERVICE_ACCOUNT_JSON` to send messages using the FCM HTTP v1 API.

### B. OIDC Mobile Client Registration
The backend REST API is secured with OIDC JWTs issued by `auth.adolfrey.com`. A native mobile client registration is required:
*   **Allowed Grant Types**: Authorization Code with PKCE (Proof Key for Code Exchange)
*   **Redirect URI**: `com.adolfrey.biketracker:/oauth2redirect`
*   **Required Scope**: `api://bike-tracker-api/user`
*   **Client ID**: To be registered (e.g., `bike-tracker-android-app`)
*   *Note: Native mobile clients must not use a client secret, as it cannot be kept secure in compiled application code.*

---

## 3. Backend Changes

To support the custom Android app, the Azure Functions backend must be updated to store device tokens and dispatch pushes.

### A. New Cosmos DB Container: `DeviceTokens`
Create a new container in your `AntigravityDb` Cosmos database:
*   **Container Name**: `DeviceTokens`
*   **Partition Key**: `/userId`
*   **Document Schema**:
    ```json
    {
      "id": "fcm_token_hash_or_uuid",
      "userId": "subject_claim_from_jwt",
      "fcmToken": "string",
      "platform": "android",
      "registeredAt": "ISO-8601",
      "lastActiveAt": "ISO-8601"
    }
    ```

### B. New REST Endpoints in `backend/function_app.py`
Two new HTTP-triggered endpoints (JWT-authenticated) must be added:

1.  `POST /api/devices/register-token`
    *   Registers or updates an FCM token for the authenticated user.
    *   Payload: `{"fcmToken": "string", "platform": "android"}`
2.  `DELETE /api/devices/register-token`
    *   Unregisters the FCM token when the user logs out.
    *   Payload: `{"fcmToken": "string"}`

### C. [NEW] `backend/services/fcm_service.py`
Create a new service responsible for authenticating with Google APIs and dispatching push notifications via the modern **FCM HTTP v1 API**.

*   **OAuth2 Token Retrieval**: Uses `google-auth` library to authenticate via the service account JSON and retrieve short-lived bearer tokens for scope `https://www.googleapis.com/auth/firebase.messaging`.
*   **Endpoint**: `https://fcm.googleapis.com/v1/projects/{FIREBASE_PROJECT_ID}/messages:send`
*   **Payload Construction**:
    *   The service must send **Data-only** messages (the JSON has a `data` block but no `notification` block). This ensures that the Android OS passes the payload directly to our app background service instead of displaying a standard system notification.
    *   **Priority Setup**: Set `android.priority` to `"high"` and `android.ttl` to `"0s"` (deliver immediately, do not queue/throttle).
    ```json
    {
      "message": {
        "token": "<DEVICE_FCM_TOKEN>",
        "data": {
          "event": "unauthorized_movement",
          "deviceId": "17026310059",
          "timestamp": "2026-07-16T12:00:00Z",
          "speed": "12.4",
          "lat": "-6.12345",
          "lng": "106.12345",
          "batteryLevel": "84",
          "isOnline": "true"
        },
        "android": {
          "priority": "high",
          "ttl": "0s"
        }
      }
    }
    ```

### D. Timer Trigger Integration in `function_app.py`
In `poll_telemetry` (~line 191-195), if an event is detected (`eventTriggered` is not null):
1.  Read all registered FCM tokens from Cosmos DB.
2.  Instantiate `FcmService`.
3.  Map the event to priority:
    *   `unauthorized_movement` → High Priority (forces full-screen alarm overlay).
    *   All other events (`movement_started`, `movement_stopped`, `engine_off`, `conn_lost`, `conn_restore`) → Normal Priority (standard heads-up notification).
4.  Asynchronously dispatch pushes to all registered tokens.

### E. Configuration Environment Variables (`local.settings.json`)
```json
"FCM_ENABLED": "true",
"FIREBASE_PROJECT_ID": "your-firebase-project-id",
"FCM_SERVICE_ACCOUNT_JSON": "path/to/firebase-service-account.json"
```

---

## 4. Native Android App Architecture

The app is built natively in **Kotlin** utilizing **Jetpack Compose** for a highly responsive UI, structured in an MVVM (Model-View-ViewModel) architectural pattern.

### A. Core Gradle Dependencies
```kotlin
dependencies {
    // Jetpack Compose & Material 3
    implementation("androidx.compose.ui:ui:1.6.0")
    implementation("androidx.compose.material3:material3:1.2.0")
    
    // OIDC Auth (AppAuth)
    implementation("net.openid:appauth:0.11.1")
    
    // Firebase Messaging
    implementation(platform("com.google.firebase:firebase-bom:32.8.0"))
    implementation("com.google.firebase:firebase-messaging-ktx")
    
    // Networking & Storage
    implementation("com.squareup.retrofit2:retrofit:2.9.0")
    implementation("com.squareup.retrofit2:converter-gson:2.9.0")
    implementation("androidx.datastore:datastore-preferences:1.0.0")
}
```

### B. Required Manifest Permissions
```xml
<manifest xmlns:android="http://schemas.android.com/apk/manifest"
    package="com.adolfrey.biketracker">

    <!-- Allow push messages in background -->
    <uses-permission android:android:name="android.permission.INTERNET" />
    <uses-permission android:name="android.permission.WAKE_LOCK" />
    
    <!-- Alarm & Full-Screen Takeover -->
    <uses-permission android:name="android.permission.USE_FULL_SCREEN_INTENT" />
    <uses-permission android:name="android.permission.DISABLE_KEYGUARD" />
    
    <!-- Keep sound looping in background on Android 14+ -->
    <uses-permission android:name="android.permission.FOREGROUND_SERVICE" />
    <uses-permission android:name="android.permission.FOREGROUND_SERVICE_MEDIA_PLAYBACK" />
    
    <!-- Android 13+ Notification Prompt -->
    <uses-permission android:name="android.permission.POST_NOTIFICATIONS" />

    <application ...>
        <service
            android:name=".push.FcmPushService"
            android:exported="false">
            <intent-filter>
                <action android:name="com.google.firebase.MESSAGING_EVENT" />
            </intent-filter>
        </service>
        
        <service
            android:name=".push.AlarmSoundService"
            android:foregroundServiceType="mediaPlayback"
            android:exported="false" />

        <activity
            android:name=".ui.AlarmActivity"
            android:showOnLockScreen="true"
            android:turnScreenOn="true"
            android:showWhenLocked="true"
            android:excludeFromRecents="true"
            android:launchMode="singleInstance"
            android:exported="false" />
    </application>
</manifest>
```

---

## 5. Native Full-Screen Alarm Implementation

This is the central feature that replicates an incoming call or physical alarm screen.

### A. Step 1: Receiving the FCM Message (`FcmPushService.kt`)
```kotlin
class FcmPushService : FirebaseMessagingService() {
    override fun onMessageReceived(remoteMessage: RemoteMessage) {
        val event = remoteMessage.data["event"] ?: return
        val speed = remoteMessage.data["speed"] ?: "0"
        
        if (event == "unauthorized_movement") {
            triggerFullScreenAlarm(event, speed)
        } else {
            triggerStandardNotification(event, speed)
        }
    }

    private fun triggerFullScreenAlarm(event: String, speed: String) {
        val channelId = "critical_alarms_channel"
        val notificationManager = getSystemService(Context.NOTIFICATION_SERVICE) as NotificationManager

        // 1. Create High-Importance Channel (Android 8.0+)
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.O) {
            val channel = NotificationChannel(
                channelId, "Critical Vehicle Alarms",
                NotificationManager.IMPORTANCE_HIGH
            ).apply {
                lockscreenVisibility = Notification.VISIBILITY_PUBLIC
                enableVibration(true)
                bypassDnd(true) // Attempt to bypass Do Not Disturb
            }
            notificationManager.createNotificationChannel(channel)
        }

        // 2. Prepare Intent to open full-screen Activity
        val fullScreenIntent = Intent(this, AlarmActivity::class.java).apply {
            flags = Intent.FLAG_ACTIVITY_NEW_TASK or Intent.FLAG_ACTIVITY_CLEAR_TOP
            putExtra("event", event)
            putExtra("speed", speed)
        }
        val fullScreenPendingIntent = PendingIntent.getActivity(
            this, 0, fullScreenIntent,
            PendingIntent.FLAG_UPDATE_CURRENT or PendingIntent.FLAG_IMMUTABLE
        )

        // 3. Build Notification with Full-Screen Intent
        val notification = NotificationCompat.Builder(this, channelId)
            .setSmallIcon(R.drawable.ic_alert)
            .setContentTitle("🚨 VEHICLE ALARM 🚨")
            .setContentText("Unauthorized movement detected! Speed: $speed km/h")
            .setPriority(NotificationCompat.PRIORITY_MAX)
            .setCategory(NotificationCompat.CATEGORY_CALL) // Treat like a telephone call
            .setFullScreenIntent(fullScreenPendingIntent, true) // Force full-screen display
            .setAutoCancel(false)
            .setOngoing(true)
            .build()

        // 4. Start Foreground Service to loop sound safely
        val serviceIntent = Intent(this, AlarmSoundService::class.java)
        ContextCompat.startForegroundService(this, serviceIntent)

        // 5. Fire notification (Android wakes up the screen and starts AlarmActivity)
        notificationManager.notify(1001, notification)
    }
}
```

### B. Step 2: Bypassing Lock Screen (`AlarmActivity.kt`)
To guarantee that our Jetpack Compose layout appears *directly* over the lock screen, we configure window attributes inside `onCreate`:

```kotlin
class AlarmActivity : ComponentActivity() {
    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        
        // Flags to turn screen on and show activity over keyguard/lockscreen
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.O_MR1) {
            setShowWhenLocked(true)
            setTurnScreenOn(true)
            val keyguardManager = getSystemService(Context.KEYGUARD_SERVICE) as KeyguardManager
            keyguardManager.requestDismissKeyguard(this, null)
        } else {
            window.addFlags(
                WindowManager.LayoutParams.FLAG_SHOW_WHEN_LOCKED or
                WindowManager.LayoutParams.FLAG_TURN_SCREEN_ON or
                WindowManager.LayoutParams.FLAG_KEEP_SCREEN_ON or
                WindowManager.LayoutParams.FLAG_DISMISS_KEYGUARD
            )
        }

        setContent {
            MaterialTheme {
                AlarmScreen(
                    event = intent.getStringExtra("event") ?: "ALARM",
                    speed = intent.getStringExtra("speed") ?: "0",
                    onDismiss = { dismissAlarm() }
                )
            }
        }
    }

    private fun dismissAlarm() {
        // 1. Stop looping sound service
        stopService(Intent(this, AlarmSoundService::class.java))
        
        // 2. Clear notification
        val notificationManager = getSystemService(Context.NOTIFICATION_SERVICE) as NotificationManager
        notificationManager.cancel(1001)
        
        // 3. Close screen
        finish()
    }
}
```

### C. Step 3: Loop Sound (`AlarmSoundService.kt`)
This service runs in the foreground to keep the alarm sound playing seamlessly, ensuring it isn't throttled or killed mid-ring.

```kotlin
class AlarmSoundService : Service() {
    private var mediaPlayer: MediaPlayer? = null

    override fun onStartCommand(intent: Intent?, flags: Int, startId: Int): Int {
        // Build a mandatory low-importance notification to satisfy foreground service requirements
        val notification = NotificationCompat.Builder(this, "critical_alarms_channel")
            .setContentTitle("Vehicle Alarm Sounding")
            .setSmallIcon(R.drawable.ic_sound)
            .setPriority(NotificationCompat.PRIORITY_LOW)
            .build()
        
        startForeground(1002, notification)

        // Play alarm loop on STREAM_ALARM (bypasses silent/ringer switches)
        mediaPlayer = MediaPlayer().apply {
            setAudioAttributes(
                AudioAttributes.Builder()
                    .setContentType(AudioAttributes.CONTENT_TYPE_SONIFICATION)
                    .setUsage(AudioAttributes.USAGE_ALARM)
                    .build()
            )
            setDataSource(this@AlarmSoundService, RingtoneManager.getDefaultUri(RingtoneManager.TYPE_ALARM))
            isLooping = true
            prepare()
            start()
        }
        return START_STICKY
    }

    override fun onDestroy() {
        mediaPlayer?.stop()
        mediaPlayer?.release()
        super.onDestroy()
    }

    override fun onBind(intent: Intent?) = null
}
```

---

## 6. App UI Specification (Jetpack Compose)

The companion application implements exactly two screens:

### Screen A: Alarm Activity Layout
*   **Visual Style**: Full-bleed flashing red background with high contrast white/yellow typography.
*   **Elements**:
    *   Large hazard icon (`🚨`).
    *   Flashing text: `"SECURITY BREACH"`.
    *   Dynamic readout: `"Unauthorized Movement Detected"`.
    *   Vehicle Speed indicator (e.g., `12.4 km/h`).
    *   Plain text coordinates display for immediate location awareness.
*   **Interactions**:
    *   A massive, distinct **"DISMISS ALARM"** button centered at the bottom. Tapping stops the siren and closes the activity immediately.

### Screen B: Minimal Status Dashboard
*   **Visual Style**: Clean Material Design 3 grid showing current telemetry status cards.
*   **Elements**:
    *   **Device Status Card**: Online/Offline badge with timestamp of last contact.
    *   **Ignition Card**: Key ON/OFF status with color indicators (Green for ON, Grey for OFF).
    *   **Speed Card**: Large typography displaying current velocity (e.g., `0.0 km/h`).
    *   **Battery Card**: Battery indicator with voltage or percentage (e.g., `84%`).
    *   **Location Card**: Numeric Lat/Lng with a "Copy Coordinates" button.
*   **Interactions**:
    *   **Pull-to-refresh** gesture on the dashboard to pull the latest state instantly.
    *   **"Lock/Unlock Ignition" button**: A post request directly triggering `/api/device/command` (with command PIN entry popup dialog) to let you disable/restore the starter.
    *   **Logout Button**: Clears OIDC tokens and calls the DELETE register-token endpoint to stop pushing alerts to the device.

---

## 7. Verification Plan

### A. Automated Backend Tests
Unit tests in `backend/tests/test_fcm_service.py` to assert:
*   FCM configuration initializes correctly.
*   Priority mapping converts `unauthorized_movement` to `high` and other events to `normal` priority.
*   FCM payload matches schema exactly.

### B. Manual Push Tooling
A debug script `backend/send_test_push.py` will be created:
*   Bypasses the timer-trigger, reads a test registration token, and issues an immediate mock `unauthorized_movement` data payload.
*   Used to verify the Android device wakes up and triggers the alarm screen immediately without waiting for a real OBD2 trigger.

### C. Android Device Test Matrix
Verification steps on physical Android device:
1.  **Warm State Verification**: App open, device unlocked. Trigger alarm. Assert heads-up notification drops down and alarm siren loops.
2.  **Lock Screen Wake Verification**: App killed, phone screen off and locked. Trigger alarm. Assert screen turns on, sound plays, and full-screen red alarm activity displays over the locked screen.
3.  **Do Not Disturb (DND) Verification**: Put phone in total silence (DND). Trigger alarm. Assert sound plays at maximum volume on the alarm stream regardless of system mute.
4.  **Dismissal Verification**: Tap "Dismiss Alarm" on the full-screen overlay. Assert that:
    *   Sound ceases instantly.
    *   Full-screen overlay activity exits.
    *   System notification is cancelled.
