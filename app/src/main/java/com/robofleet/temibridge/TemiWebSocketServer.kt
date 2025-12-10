package com.robofleet.temibridge

import android.util.Log
import com.google.gson.Gson
import com.google.gson.JsonObject
import fi.iki.elonen.NanoHTTPD
import fi.iki.elonen.NanoWSD
import java.io.IOException

/**
 * WebSocket server running on Android
 * Listens on port 8080 by default
 */
class TemiWebSocketServer(
    private val port: Int = 8080,
    private val commandHandler: (String, JsonObject) -> Unit
) : NanoWSD(port) {

    private val TAG = "TemiWebSocketServer"
    private val gson = Gson()
    private val activeConnections = mutableSetOf<TemiWebSocket>()

    init {
        Log.i(TAG, "WebSocket server initialized on port $port")
    }

    override fun openWebSocket(handshake: IHTTPSession): WebSocket {
        Log.i(TAG, "New WebSocket connection from ${handshake.remoteIpAddress}")
        return TemiWebSocket(handshake)
    }

    fun broadcast(message: String) {
        val deadConnections = mutableSetOf<TemiWebSocket>()

        activeConnections.forEach { socket ->
            try {
                socket.send(message)
            } catch (e: IOException) {
                Log.e(TAG, "Failed to send to client, marking for removal", e)
                deadConnections.add(socket)
            }
        }

        activeConnections.removeAll(deadConnections)

        if (deadConnections.isNotEmpty()) {
            Log.w(TAG, "Removed ${deadConnections.size} dead connections")
        }
    }

    fun sendToClient(client: TemiWebSocket, message: String) {
        try {
            client.send(message)
        } catch (e: IOException) {
            Log.e(TAG, "Failed to send message to client", e)
            activeConnections.remove(client)
        }
    }

    fun getConnectionCount(): Int = activeConnections.size

    inner class TemiWebSocket(handshake: IHTTPSession) : WebSocket(handshake) {

        override fun onOpen() {
            activeConnections.add(this)
            Log.i(TAG, "WebSocket opened. Total connections: ${activeConnections.size}")

            try {
                val welcome = gson.toJson(mapOf(
                    "type" to "connection",
                    "status" to "connected",
                    "message" to "Connected to Temi Robot Bridge",
                    "timestamp" to System.currentTimeMillis()
                ))
                send(welcome)
            } catch (e: IOException) {
                Log.e(TAG, "Failed to send welcome message", e)
            }
        }

        override fun onClose(
            code: WebSocketFrame.CloseCode,
            reason: String?,
            initiatedByRemote: Boolean
        ) {
            activeConnections.remove(this)
            Log.i(TAG, "WebSocket closed: $reason. Remaining: ${activeConnections.size}")
        }

        override fun onMessage(message: WebSocketFrame) {
            try {
                val payload = message.textPayload
                Log.d(TAG, "Received message: $payload")

                val json = gson.fromJson(payload, JsonObject::class.java)
                val command = json.get("command")?.asString ?: "unknown"

                commandHandler(command, json)

            } catch (e: Exception) {
                Log.e(TAG, "Error processing message", e)

                try {
                    val error = gson.toJson(mapOf(
                        "type" to "error",
                        "message" to "Invalid command format: ${e.message}",
                        "timestamp" to System.currentTimeMillis()
                    ))
                    send(error)
                } catch (sendError: IOException) {
                    Log.e(TAG, "Failed to send error response", sendError)
                }
            }
        }

        override fun onPong(pong: WebSocketFrame) {
            Log.d(TAG, "Pong received")
        }

        override fun onException(exception: IOException) {
            Log.e(TAG, "WebSocket exception", exception)
            activeConnections.remove(this)
        }
    }

    override fun serve(session: IHTTPSession): Response {
        val uri = session.uri

        // Check if this is a WebSocket upgrade request
        val headers = session.headers
        val upgrade = headers["upgrade"]

        if (upgrade != null && upgrade.equals("websocket", ignoreCase = true)) {
            // Let the parent class handle WebSocket upgrade
            return super.serve(session)
        }

        // Handle regular HTTP requests
        return when (uri) {
            "/health" -> {
                val status = mapOf(
                    "status" to "online",
                    "connections" to activeConnections.size,
                    "port" to port,
                    "timestamp" to System.currentTimeMillis()
                )
                newFixedLengthResponse(
                    Response.Status.OK,
                    "application/json",
                    gson.toJson(status)
                )
            }

            "/info" -> {
                val info = mapOf(
                    "service" to "Temi Robot Bridge",
                    "version" to "1.0",
                    "websocket_port" to port,
                    "active_connections" to activeConnections.size
                )
                newFixedLengthResponse(
                    Response.Status.OK,
                    "application/json",
                    gson.toJson(info)
                )
            }

            else -> {
                newFixedLengthResponse(
                    Response.Status.NOT_FOUND,
                    "text/plain",
                    "Endpoint not found. Try /health or connect via WebSocket"
                )
            }
        }
    }
}