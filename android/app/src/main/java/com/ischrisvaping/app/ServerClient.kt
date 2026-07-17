package com.ischrisvaping.app

import android.content.Context
import android.os.Handler
import android.os.Looper
import android.util.Log
import android.widget.Toast
import org.json.JSONObject
import java.io.OutputStreamWriter
import java.net.HttpURLConnection
import java.net.URL
import java.util.concurrent.Executors
import java.util.concurrent.LinkedBlockingDeque
import java.util.concurrent.ScheduledExecutorService
import java.util.concurrent.TimeUnit

private data class VapeEventPayload(
    val coil: String,
    val event: String,
    val vapeName: String,
    val timestampMs: Long,
)

class ServerClient(private val context: Context) {

    companion object {
        private const val TAG = "ServerClient"
        private const val CONNECT_TIMEOUT_MS = 10000
        private const val READ_TIMEOUT_MS = 10000
        private const val MAX_PENDING_EVENTS = 200
        private const val RETRY_INTERVAL_SECONDS = 5L
    }

    private val httpExecutor = Executors.newSingleThreadExecutor()
    private val retryScheduler: ScheduledExecutorService = Executors.newSingleThreadScheduledExecutor()
    private val mainHandler = Handler(Looper.getMainLooper())
    private val pendingEvents = LinkedBlockingDeque<VapeEventPayload>(MAX_PENDING_EVENTS)

    init {
        retryScheduler.scheduleWithFixedDelay({
            if (pendingEvents.isNotEmpty()) {
                httpExecutor.execute { flushPendingEvents() }
            }
        }, RETRY_INTERVAL_SECONDS, RETRY_INTERVAL_SECONDS, TimeUnit.SECONDS)
    }

    private val serverUrl: String
        get() = context.getSharedPreferences("vape_config", Context.MODE_PRIVATE)
            .getString("server_url", "") ?: ""

    private val authToken: String
        get() = context.getSharedPreferences("vape_config", Context.MODE_PRIVATE)
            .getString("auth_token", "") ?: ""

    fun postVapeEvent(coil: String, event: String, vapeName: String) {
        val payload = VapeEventPayload(coil, event, vapeName, System.currentTimeMillis())
        httpExecutor.execute {
            flushPendingEvents()
            val sent = if (pendingEvents.isEmpty()) {
                trySendVapeEvent(payload, notifyErrors = true)
            } else {
                false
            }
            if (!sent) {
                if (!pendingEvents.offerLast(payload)) {
                    // Queue full: drop oldest to make room for the new event
                    pendingEvents.pollFirst()
                    pendingEvents.offerLast(payload)
                    Log.w(TAG, "Pending queue full, dropped oldest event")
                }
                Log.d(TAG, "Queued event for retry: $vapeName $coil:$event (queue size: ${pendingEvents.size})")
            }
        }
    }

    private fun flushPendingEvents() {
        while (pendingEvents.isNotEmpty()) {
            val pending = pendingEvents.peekFirst() ?: break
            if (trySendVapeEvent(pending, notifyErrors = false)) {
                pendingEvents.pollFirst()
                Log.d(TAG, "Flushed pending event: ${pending.vapeName} ${pending.coil}:${pending.event}")
            } else {
                break
            }
        }
    }

    private fun trySendVapeEvent(payload: VapeEventPayload, notifyErrors: Boolean): Boolean {
        if (serverUrl.isBlank() || authToken.isBlank()) {
            Log.w(TAG, "Server URL or auth token not configured, skipping post")
            return true // Treat as success so event is not buffered
        }
        val url = URL("$serverUrl/vape-update")
        val connection = url.openConnection() as HttpURLConnection
        return try {
            connection.requestMethod = "POST"
            connection.setRequestProperty("Content-Type", "application/json")
            connection.setRequestProperty("Authorization", "Bearer $authToken")
            connection.doOutput = true
            connection.connectTimeout = CONNECT_TIMEOUT_MS
            connection.readTimeout = READ_TIMEOUT_MS

            val json = JSONObject().apply {
                put("coil", payload.coil)
                put("event", payload.event)
                put("vape_name", payload.vapeName)
                put("timestamp", payload.timestampMs)
            }.toString()

            OutputStreamWriter(connection.outputStream).use { writer ->
                writer.write(json)
                writer.flush()
            }

            val responseCode = connection.responseCode
            Log.d(TAG, "Server response: $responseCode for ${payload.vapeName} ${payload.coil}:${payload.event}")
            if (responseCode in 200..299) {
                true
            } else {
                if (notifyErrors) showToast("Server error: $responseCode")
                false
            }
        } catch (e: Exception) {
            Log.e(TAG, "Failed to post to server: ${e.message}")
            if (notifyErrors) showToast(e.message ?: "Unknown error")
            false
        } finally {
            connection.disconnect()
        }
    }

    fun postRenameDevice(oldName: String?, newName: String, onSuccess: () -> Unit) {
        httpExecutor.execute {
            if (serverUrl.isBlank() || authToken.isBlank()) {
                Log.w(TAG, "Server URL or auth token not configured, renaming locally only")
                mainHandler.post { onSuccess() }
                return@execute
            }
            val url = URL("$serverUrl/device/rename")
            val connection = url.openConnection() as HttpURLConnection
            try {
                connection.requestMethod = "POST"
                connection.setRequestProperty("Content-Type", "application/json")
                connection.setRequestProperty("Authorization", "Bearer $authToken")
                connection.doOutput = true
                connection.connectTimeout = CONNECT_TIMEOUT_MS
                connection.readTimeout = READ_TIMEOUT_MS

                val json = JSONObject().apply {
                    if (oldName != null) put("old_name", oldName)
                    put("new_name", newName)
                }.toString()

                OutputStreamWriter(connection.outputStream).use { writer ->
                    writer.write(json)
                    writer.flush()
                }

                val responseCode = connection.responseCode
                Log.d(TAG, "Rename response: $responseCode for $oldName -> $newName")
                if (responseCode in 200..299) {
                    mainHandler.post { onSuccess() }
                } else {
                    showToast("Rename failed: server error $responseCode")
                }
            } catch (e: Exception) {
                Log.e(TAG, "Failed to post rename to server: ${e.message}")
                showToast("Rename failed: ${e.message ?: "Unknown error"}")
            } finally {
                connection.disconnect()
            }
        }
    }

    fun shutdown() {
        retryScheduler.shutdown()
        httpExecutor.shutdown()
        retryScheduler.awaitTermination(2, TimeUnit.SECONDS)
        httpExecutor.awaitTermination(2, TimeUnit.SECONDS)
    }

    private fun showToast(message: String) {
        mainHandler.post {
            Toast.makeText(context, message, Toast.LENGTH_SHORT).show()
        }
    }
}
