package com.robofleet.temibridge

import android.content.Context
import android.util.Log
import com.google.gson.Gson
import com.robotemi.sdk.Robot
import com.robotemi.sdk.TtsRequest
import com.robotemi.sdk.listeners.OnGoToLocationStatusChangedListener
import com.robotemi.sdk.listeners.OnLocationsUpdatedListener
import com.robotemi.sdk.listeners.OnRobotReadyListener
import com.robotemi.sdk.navigation.listener.OnCurrentPositionChangedListener
import com.robotemi.sdk.navigation.model.Position
import kotlinx.coroutines.*

class TemiRobotManager(
    private val context: Context,
    private val onStatusUpdate: (Map<String, Any>) -> Unit
) : OnRobotReadyListener,
    OnGoToLocationStatusChangedListener,
    OnLocationsUpdatedListener,
    OnCurrentPositionChangedListener {

    private val TAG = "TemiRobotManager"
    private val gson = Gson()

    private var robot: Robot? = null
    private var isReady = false
    private var currentLocation: String = "unknown"
    private var currentStatus: String = "initializing"
    private var batteryPercentage: Int = 0
    private var isCharging: Boolean = false

    private val scope = CoroutineScope(Dispatchers.Default + SupervisorJob())
    private var batteryMonitorJob: Job? = null

    init {
        Log.i(TAG, "TemiRobotManager initializing...")
        initializeRobot()
    }

    private fun initializeRobot() {
        try {
            robot = Robot.getInstance()

            robot?.addOnRobotReadyListener(this)
            robot?.addOnGoToLocationStatusChangedListener(this)
            robot?.addOnCurrentPositionChangedListener(this)
            robot?.addOnLocationsUpdatedListener(this)

            Log.i(TAG, "Robot instance obtained, listeners registered")
        } catch (e: Exception) {
            Log.e(TAG, "Failed to initialize robot", e)
            currentStatus = "error"
            sendStatusUpdate()
        }
    }

    override fun onRobotReady(isReady: Boolean) {
        Log.i(TAG, "Robot ready: $isReady")
        this.isReady = isReady

        if (isReady) {
            currentStatus = "idle"

            updateBatteryInfo()
            updateLocationInfo()

            startBatteryMonitoring()

            val serialNumber = robot?.serialNumber ?: "UNKNOWN"
            Log.i(TAG, "Robot SN: $serialNumber")

        } else {
            currentStatus = "not_ready"
            stopBatteryMonitoring()
        }

        sendStatusUpdate()
    }

    override fun onGoToLocationStatusChanged(
        location: String,
        status: String,
        descriptionId: Int,
        description: String
    ) {
        Log.i(TAG, "GoTo status: $location -> $status ($description)")

        when (status) {
            "start" -> {
                currentStatus = "moving"
                currentLocation = "traveling_to_$location"
            }
            "going" -> {
                currentStatus = "moving"
            }
            "complete" -> {
                currentStatus = "idle"
                currentLocation = location
            }
            "abort" -> {
                currentStatus = "idle"
                Log.w(TAG, "Navigation aborted: $description")
            }
            "calculating" -> {
                currentStatus = "calculating_path"
            }
        }

        sendStatusUpdate(mapOf(
            "event" to "navigation_status",
            "location" to location,
            "status" to status,
            "description" to description
        ))
    }

    fun goToLocation(locationName: String): Boolean {
        if (!isReady) {
            Log.e(TAG, "Robot not ready")
            return false
        }

        val locations = robot?.locations ?: emptyList()

        if (!locations.contains(locationName)) {
            Log.e(TAG, "Location '$locationName' not found. Available: $locations")
            return false
        }

        Log.i(TAG, "Going to location: $locationName")
        robot?.goTo(locationName)
        return true
    }

    fun stopMovement(): Boolean {
        if (!isReady) return false

        Log.i(TAG, "Stopping movement")
        robot?.stopMovement()
        currentStatus = "idle"
        sendStatusUpdate()
        return true
    }

    override fun onLocationsUpdated(locations: List<String>) {
        Log.i(TAG, "Locations updated: $locations")

        sendStatusUpdate(mapOf(
            "event" to "locations_updated",
            "locations" to locations
        ))
    }

    fun getLocations(): List<String> {
        return robot?.locations ?: emptyList()
    }

    fun saveLocation(locationName: String): Boolean {
        if (!isReady) {
            Log.e(TAG, "Robot not ready")
            return false
        }

        Log.i(TAG, "Saving location: $locationName")
        val result = robot?.saveLocation(locationName)

        if (result == true) {
            Log.i(TAG, "Location saved successfully: $locationName")
        } else {
            Log.e(TAG, "Failed to save location: $locationName")
        }

        return result ?: false
    }

    fun deleteLocation(locationName: String): Boolean {
        if (!isReady) return false

        Log.i(TAG, "Deleting location: $locationName")
        val result = robot?.deleteLocation(locationName)
        return result ?: false
    }

    override fun onCurrentPositionChanged(position: Position) {
        val now = System.currentTimeMillis()
        if (now - lastPositionUpdate > 5000) {
            sendStatusUpdate(mapOf(
                "event" to "position_update",
                "x" to position.x,
                "y" to position.y,
                "yaw" to position.yaw,
                "tilt" to position.tiltAngle
            ))
            lastPositionUpdate = now
        }
    }

    private var lastPositionUpdate: Long = 0

    private fun startBatteryMonitoring() {
        batteryMonitorJob?.cancel()

        batteryMonitorJob = scope.launch {
            while (isActive) {
                updateBatteryInfo()
                delay(10000)
            }
        }

        Log.i(TAG, "Battery monitoring started")
    }

    private fun stopBatteryMonitoring() {
        batteryMonitorJob?.cancel()
        Log.i(TAG, "Battery monitoring stopped")
    }

    private fun updateBatteryInfo() {
        robot?.let { r ->
            val batteryData = r.batteryData
            batteryPercentage = batteryData?.battery2Level?: 0
            isCharging = batteryData?.isCharging ?: false
        }
    }

    fun speak(text: String, showText: Boolean = true) {
        if (!isReady) return

        val ttsRequest = TtsRequest.create(text, showText)
        robot?.speak(ttsRequest)
    }

    fun tiltAngle(degrees: Int) {
        if (!isReady) return

        val clampedDegrees = degrees.coerceIn(-25, 55)
        robot?.tiltAngle(clampedDegrees)
    }

    fun turnBy(degrees: Int) {
        if (!isReady) return

        robot?.turnBy(degrees)
    }

    fun getSerialNumber(): String {
        return robot?.serialNumber ?: "UNKNOWN"
    }

    private fun updateLocationInfo() {
        currentLocation = (robot?.locations ?: "unknown") as String
    }

    private fun sendStatusUpdate(extraData: Map<String, Any> = emptyMap()) {
        val status = mutableMapOf<String, Any>(
            "status" to currentStatus,
            "battery" to batteryPercentage,
            "charging" to isCharging,
            "location" to currentLocation,
            "ready" to isReady,
            "serial_number" to getSerialNumber(),
            "timestamp" to System.currentTimeMillis()
        )

        status.putAll(extraData)

        onStatusUpdate(status)
    }

    fun cleanup() {
        Log.i(TAG, "Cleaning up TemiRobotManager")

        stopBatteryMonitoring()
        scope.cancel()

        robot?.let { r ->
            r.removeOnRobotReadyListener(this)
            r.removeOnGoToLocationStatusChangedListener(this)
            r.removeOnCurrentPositionChangedListener(this)
            r.removeOnLocationsUpdateListener(this)
        }
    }
}