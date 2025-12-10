package com.robofleet.temibridge

import android.content.Intent
import android.os.Build
import android.os.Bundle
import android.os.Handler
import android.os.Looper
import android.util.Log
import android.view.View
import android.widget.Button
import android.widget.TextView
import androidx.appcompat.app.AppCompatActivity
import androidx.cardview.widget.CardView
import com.robotemi.sdk.Robot
import com.robotemi.sdk.permission.Permission

class MainActivity : AppCompatActivity() {

    private val TAG = "MainActivity"

    private lateinit var statusText: TextView
    private lateinit var startButton: Button
    private lateinit var stopButton: Button
    private lateinit var infoCard: CardView
    private lateinit var websocketUrl: TextView
    private lateinit var restUrl: TextView
    private lateinit var serialNumber: TextView
    private lateinit var connectionStatusText: TextView
    private lateinit var statusIndicator: View

    private var serviceRunning = false
    private val handler = Handler(Looper.getMainLooper())
    private var updateRunnable: Runnable? = null

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        setContentView(R.layout.activity_main)

        Log.i(TAG, "MainActivity onCreate")

        initializeViews()
        requestTemiPermissions()

        if (shouldAutoStart()) {
            startBridgeService()
        }

        startPeriodicUIUpdate()
    }

    private fun initializeViews() {
        statusText = findViewById(R.id.statusText)
        startButton = findViewById(R.id.startButton)
        stopButton = findViewById(R.id.stopButton)
        infoCard = findViewById(R.id.infoCard)
        websocketUrl = findViewById(R.id.websocketUrl)
        restUrl = findViewById(R.id.restUrl)
        serialNumber = findViewById(R.id.serialNumber)
        connectionStatusText = findViewById(R.id.connectionStatusText)
        statusIndicator = findViewById(R.id.statusIndicator)

        startButton.setOnClickListener {
            startBridgeService()
        }

        stopButton.setOnClickListener {
            stopBridgeService()
        }

        serialNumber.text = getRobotSerial()

        updateUI()
    }

    private fun requestTemiPermissions() {
        try {
            val robot = Robot.getInstance()
            val permissions = listOf(
                Permission.MAP,
                Permission.SETTINGS,
                Permission.SEQUENCE
            )
            robot.requestPermissions(permissions, 0)
        } catch (e: Exception) {
            Log.e(TAG, "Failed to request permissions", e)
        }
    }

    private fun startBridgeService() {
        Log.i(TAG, "Starting bridge service")

        val serviceIntent = Intent(this, TemiWebSocketService::class.java)

        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.O) {
            startForegroundService(serviceIntent)
        } else {
            startService(serviceIntent)
        }

        serviceRunning = true
        updateUI()

        saveAutoStartPreference(true)

        statusText.text = "Bridge Starting..."
        statusText.setTextColor(getColor(android.R.color.holo_orange_dark))

        handler.postDelayed({
            updateUI()

            handler.postDelayed({
                moveTaskToBack(true)
                Log.i(TAG, "App moved to background, service continues running")
            }, 2000)
        }, 1000)
    }

    private fun stopBridgeService() {
        Log.i(TAG, "Stopping bridge service")

        val serviceIntent = Intent(this, TemiWebSocketService::class.java)
        stopService(serviceIntent)

        serviceRunning = false
        saveAutoStartPreference(false)
        updateUI()
    }

    private fun updateUI() {
        if (serviceRunning || isServiceRunning()) {
            serviceRunning = true

            statusText.text = "Bridge Running"
            statusText.setTextColor(getColor(android.R.color.holo_green_dark))

            startButton.isEnabled = false
            stopButton.isEnabled = true

            infoCard.visibility = View.VISIBLE

            val ipAddress = getIPAddress()
            websocketUrl.text = "ws://$ipAddress:8080"
            restUrl.text = "http://$ipAddress:8080/health"

            statusIndicator.setBackgroundResource(R.drawable.status_indicator_online)
            connectionStatusText.text = "Online"

        } else {
            statusText.text = "Bridge Stopped"
            statusText.setTextColor(getColor(android.R.color.holo_red_dark))

            startButton.isEnabled = true
            stopButton.isEnabled = false

            infoCard.visibility = View.GONE

            statusIndicator.setBackgroundResource(R.drawable.status_indicator)
            connectionStatusText.text = "Offline"
        }
    }

    private fun isServiceRunning(): Boolean {
        val manager = getSystemService(ACTIVITY_SERVICE) as android.app.ActivityManager
        @Suppress("DEPRECATION")
        for (service in manager.getRunningServices(Int.MAX_VALUE)) {
            if (TemiWebSocketService::class.java.name == service.service.className) {
                return true
            }
        }
        return false
    }

    private fun getIPAddress(): String {
        try {
            val interfaces = java.net.NetworkInterface.getNetworkInterfaces()
            while (interfaces.hasMoreElements()) {
                val networkInterface = interfaces.nextElement()
                val addresses = networkInterface.inetAddresses

                while (addresses.hasMoreElements()) {
                    val address = addresses.nextElement()

                    if (!address.isLoopbackAddress && address is java.net.Inet4Address) {
                        return address.hostAddress ?: "unknown"
                    }
                }
            }
        } catch (e: Exception) {
            Log.e(TAG, "Failed to get IP address", e)
        }

        return "unknown"
    }

    private fun getRobotSerial(): String {
        return try {
            Robot.getInstance().serialNumber ?: "UNKNOWN"
        } catch (e: Exception) {
            "UNKNOWN"
        }
    }

    private fun shouldAutoStart(): Boolean {
        val prefs = getSharedPreferences("temi_bridge", MODE_PRIVATE)
        return prefs.getBoolean("auto_start", false)
    }

    private fun saveAutoStartPreference(autoStart: Boolean) {
        val prefs = getSharedPreferences("temi_bridge", MODE_PRIVATE)
        prefs.edit().putBoolean("auto_start", autoStart).apply()
    }

    private fun startPeriodicUIUpdate() {
        updateRunnable = object : Runnable {
            override fun run() {
                updateUI()
                handler.postDelayed(this, 2000)
            }
        }
        handler.post(updateRunnable!!)
    }

    private fun stopPeriodicUIUpdate() {
        updateRunnable?.let {
            handler.removeCallbacks(it)
        }
    }

    override fun onResume() {
        super.onResume()
        updateUI()
        startPeriodicUIUpdate()
    }

    override fun onPause() {
        super.onPause()
        stopPeriodicUIUpdate()
    }

    override fun onDestroy() {
        super.onDestroy()
        stopPeriodicUIUpdate()
        Log.i(TAG, "MainActivity onDestroy")
    }
}