package com.robofleet.temibridge

import android.app.*
import android.content.Context
import android.content.Intent
import android.os.Build
import android.os.IBinder
import android.os.PowerManager
import android.util.Log
import androidx.core.app.NotificationCompat
import com.google.gson.Gson
import com.google.gson.JsonObject
import kotlinx.coroutines.*
import okhttp3.*
import okhttp3.MediaType.Companion.toMediaType
import okhttp3.RequestBody.Companion.toRequestBody
import java.io.IOException

class TemiWebSocketService : Service() {

    private val TAG = "TemiWebSocketService"
    private val NOTIFICATION_ID = 1001
    private val CHANNEL_ID = "temi_bridge_channel"

    private var webSocketServer: TemiWebSocketServer? = null
    private var robotManager: TemiRobotManager? = null
    private var wakeLock: PowerManager.WakeLock? = null

    private val gson = Gson()
    private val httpClient = OkHttpClient()

    // CHANGE THIS to your FastAPI server URL
    private var fastapiServerUrl = "http://192.168.0.142:8000"

    private val scope = CoroutineScope(Dispatchers.Default + SupervisorJob())
    private var statusReportJob: Job? = null

    override fun onCreate() {
        super.onCreate()
        Log.i(TAG, "Service onCreate")

        acquireWakeLock()
        createNotificationChannel()

        val notification = createNotification("Starting bridge service...")
        startForeground(NOTIFICATION_ID, notification)

        initializeComponents()
        startStatusReporting()

        Log.i(TAG, "Service fully initialized and running in background")
    }

    private fun initializeComponents() {
        try {
            robotManager = TemiRobotManager(this) { status ->
                handleRobotStatusUpdate(status)
            }

            webSocketServer = TemiWebSocketServer(port = 8080) { command, json ->
                handleWebSocketCommand(command, json)
            }

            webSocketServer?.start()
            Log.i(TAG, "WebSocket server started on port 8080")

            updateNotification("Bridge Active - Port 8080")

        } catch (e: Exception) {
            Log.e(TAG, "Failed to initialize components", e)
            updateNotification("Bridge Error - Check Logs")
        }
    }

    private fun handleWebSocketCommand(command: String, json: JsonObject) {
        Log.i(TAG, "Command received: $command")

        val response = when (command) {
            "goto" -> {
                val location = json.get("location")?.asString
                if (location != null) {
                    val success = robotManager?.goToLocation(location) ?: false
                    mapOf(
                        "command" to "goto",
                        "success" to success,
                        "location" to location,
                        "message" to if (success) "Navigation started" else "Failed to start navigation"
                    )
                } else {
                    mapOf("error" to "Missing 'location' parameter")
                }
            }

            "stop" -> {
                val success = robotManager?.stopMovement() ?: false
                mapOf(
                    "command" to "stop",
                    "success" to success,
                    "message" to "Movement stopped"
                )
            }

            "get_locations" -> {
                val locations = robotManager?.getLocations() ?: emptyList()
                mapOf(
                    "command" to "get_locations",
                    "locations" to locations
                )
            }

            "save_location" -> {
                val name = json.get("name")?.asString
                if (name != null) {
                    val success = robotManager?.saveLocation(name) ?: false
                    mapOf(
                        "command" to "save_location",
                        "success" to success,
                        "name" to name
                    )
                } else {
                    mapOf("error" to "Missing 'name' parameter")
                }
            }

            "delete_location" -> {
                val name = json.get("name")?.asString
                if (name != null) {
                    val success = robotManager?.deleteLocation(name) ?: false
                    mapOf(
                        "command" to "delete_location",
                        "success" to success,
                        "name" to name
                    )
                } else {
                    mapOf("error" to "Missing 'name' parameter")
                }
            }

            "speak" -> {
                val text = json.get("text")?.asString
                if (text != null) {
                    robotManager?.speak(text)
                    mapOf(
                        "command" to "speak",
                        "success" to true,
                        "text" to text
                    )
                } else {
                    mapOf("error" to "Missing 'text' parameter")
                }
            }

            "tilt" -> {
                val degrees = json.get("degrees")?.asInt
                if (degrees != null) {
                    robotManager?.tiltAngle(degrees)
                    mapOf(
                        "command" to "tilt",
                        "success" to true,
                        "degrees" to degrees
                    )
                } else {
                    mapOf("error" to "Missing 'degrees' parameter")
                }
            }

            "turn" -> {
                val degrees = json.get("degrees")?.asInt
                if (degrees != null) {
                    robotManager?.turnBy(degrees)
                    mapOf(
                        "command" to "turn",
                        "success" to true,
                        "degrees" to degrees
                    )
                } else {
                    mapOf("error" to "Missing 'degrees' parameter")
                }
            }

            "get_status" -> {
                getCurrentStatus()
            }

            else -> {
                mapOf("error" to "Unknown command: $command")
            }
        }

        webSocketServer?.broadcast(gson.toJson(response))
    }

    private fun handleRobotStatusUpdate(status: Map<String, Any>) {
        val message = gson.toJson(mapOf(
            "type" to "status_update",
            "data" to status
        ))
        webSocketServer?.broadcast(message)

        val battery = status["battery"] as? Int ?: 0
        val robotStatus = status["status"] as? String ?: "unknown"
        updateNotification("Battery: $battery% | $robotStatus")
    }

    private fun getCurrentStatus(): Map<String, Any> {
        return mapOf(
            "status" to (robotManager?.let { "connected" } ?: "disconnected"),
            "serial_number" to (robotManager?.getSerialNumber() ?: "UNKNOWN"),
            "locations" to (robotManager?.getLocations() ?: emptyList()),
            "websocket_port" to 8080,
            "connections" to (webSocketServer?.getConnectionCount() ?: 0),
            "timestamp" to System.currentTimeMillis()
        )
    }

    private fun startStatusReporting() {
        statusReportJob?.cancel()

        statusReportJob = scope.launch {
            delay(5000)

            while (isActive) {
                try {
                    reportStatusToFastAPI()
                } catch (e: Exception) {
                    Log.e(TAG, "Failed to report status to FastAPI", e)
                }
                delay(10000)
            }
        }
    }

    private fun reportStatusToFastAPI() {
        val serialNumber = robotManager?.getSerialNumber() ?: return

        val status = getCurrentStatus()
        val payload = mapOf(
            "sn" to serialNumber,
            "status" to status,
            "type" to "temi"
        )

        val json = gson.toJson(payload)
        val body = json.toRequestBody("application/json".toMediaType())

        val request = Request.Builder()
            .url("$fastapiServerUrl/api/v1/robot/temi/status/update")
            .post(body)
            .build()

        httpClient.newCall(request).enqueue(object : Callback {
            override fun onFailure(call: Call, e: IOException) {
                Log.w(TAG, "Failed to report to FastAPI: ${e.message}")
            }

            override fun onResponse(call: Call, response: Response) {
                if (response.isSuccessful) {
                    Log.d(TAG, "Status reported to FastAPI")
                } else {
                    Log.w(TAG, "FastAPI returned: ${response.code}")
                }
                response.close()
            }
        })
    }

    private fun createNotificationChannel() {
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.O) {
            val channel = NotificationChannel(
                CHANNEL_ID,
                "Temi Bridge Service",
                NotificationManager.IMPORTANCE_LOW
            ).apply {
                description = "Keeps Temi robot bridge running"
            }

            val notificationManager = getSystemService(NotificationManager::class.java)
            notificationManager.createNotificationChannel(channel)
        }
    }

    private fun createNotification(message: String): Notification {
        val intent = Intent(this, MainActivity::class.java)
        val pendingIntent = PendingIntent.getActivity(
            this, 0, intent,
            PendingIntent.FLAG_IMMUTABLE
        )

        return NotificationCompat.Builder(this, CHANNEL_ID)
            .setContentTitle("Temi Robot Bridge")
            .setContentText(message)
            .setSmallIcon(android.R.drawable.ic_dialog_info)
            .setContentIntent(pendingIntent)
            .setOngoing(true)
            .build()
    }

    private fun updateNotification(message: String) {
        val notification = createNotification(message)
        val notificationManager = getSystemService(NotificationManager::class.java)
        notificationManager.notify(NOTIFICATION_ID, notification)
    }

    private fun acquireWakeLock() {
        val powerManager = getSystemService(Context.POWER_SERVICE) as PowerManager
        wakeLock = powerManager.newWakeLock(
            PowerManager.PARTIAL_WAKE_LOCK,
            "TemiBridge::WakeLock"
        )
        wakeLock?.acquire()
        Log.i(TAG, "Wake lock acquired")
    }

    private fun releaseWakeLock() {
        wakeLock?.let {
            if (it.isHeld) {
                it.release()
                Log.i(TAG, "Wake lock released")
            }
        }
    }

    override fun onStartCommand(intent: Intent?, flags: Int, startId: Int): Int {
        Log.i(TAG, "Service onStartCommand")
        return START_STICKY
    }

    override fun onBind(intent: Intent?): IBinder? {
        return null
    }

    override fun onDestroy() {
        super.onDestroy()
        Log.i(TAG, "Service onDestroy")

        statusReportJob?.cancel()
        scope.cancel()

        webSocketServer?.stop()
        robotManager?.cleanup()

        releaseWakeLock()
    }
}