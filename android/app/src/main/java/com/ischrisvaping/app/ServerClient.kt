package com.ischrisvaping.app

import android.os.Handler
import android.os.Looper
import android.util.Log
import android.widget.Toast
import android.content.Context
import org.json.JSONObject
import java.io.OutputStreamWriter
import java.net.HttpURLConnection
import java.net.URL
import java.util.concurrent.Executors

class ServerClient(private val context: Context) {

    companion object {
        private const val TAG = "ServerClient"
        private const val CONNECT_TIMEOUT_MS = 10000
        private const val READ_TIMEOUT_MS = 10000
    }

    private val httpExecutor = Executors.newSingleThreadExecutor()
    private val mainHandler = Handler(Looper.getMainLooper())

    private val serverUrl: String
        get() = context.getSharedPreferences("vape_config", Context.MODE_PRIVATE)
            .getString("server_url", "") ?: ""

    private val authToken: String
        get() = context.getSharedPreferences("vape_config", Context.MODE_PRIVATE)
            .getString("auth_token", "") ?: ""

    fun postVapeEvent(coil: String, event: String, vapeName: String) {
        httpExecutor.execute {
            try {
                if (serverUrl.isBlank() || authToken.isBlank()) {
                    Log.w(TAG, "Server URL or auth token not configured, skipping post")
                    return@execute
                }
                val url = URL("$serverUrl/vape-update")
                val connection = url.openConnection() as HttpURLConnection
                connection.requestMethod = "POST"
                connection.setRequestProperty("Content-Type", "application/json")
                connection.setRequestProperty("Authorization", "Bearer $authToken")
                connection.doOutput = true
                connection.connectTimeout = CONNECT_TIMEOUT_MS
                connection.readTimeout = READ_TIMEOUT_MS

                val json = JSONObject().apply {
                    put("coil", coil)
                    put("event", event)
                    put("vape_name", vapeName)
                    put("timestamp", System.currentTimeMillis())
                }.toString()

                OutputStreamWriter(connection.outputStream).use { writer ->
                    writer.write(json)
                    writer.flush()
                }

                val responseCode = connection.responseCode
                Log.d(TAG, "Server response: $responseCode for $vapeName $coil:$event")
                if (responseCode !in 200..299) {
                    showToast("Server error: $responseCode")
                }
                connection.disconnect()
            } catch (e: Exception) {
                Log.e(TAG, "Failed to post to server: ${e.message}")
                showToast("${e.message}")
            }
        }
    }

    fun postRenameDevice(oldName: String, newName: String, onSuccess: () -> Unit) {
        httpExecutor.execute {
            try {
                if (serverUrl.isBlank() || authToken.isBlank()) {
                    Log.w(TAG, "Server URL or auth token not configured, renaming locally only")
                    mainHandler.post { onSuccess() }
                    return@execute
                }
                val url = URL("$serverUrl/device/rename")
                val connection = url.openConnection() as HttpURLConnection
                connection.requestMethod = "POST"
                connection.setRequestProperty("Content-Type", "application/json")
                connection.setRequestProperty("Authorization", "Bearer $authToken")
                connection.doOutput = true
                connection.connectTimeout = CONNECT_TIMEOUT_MS
                connection.readTimeout = READ_TIMEOUT_MS

                val json = JSONObject().apply {
                    put("old_name", oldName)
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
                connection.disconnect()
            } catch (e: Exception) {
                Log.e(TAG, "Failed to post rename to server: ${e.message}")
                showToast("Rename failed: ${e.message}")
            }
        }
    }

    fun shutdown() {
        httpExecutor.shutdown()
    }

    private fun showToast(message: String) {
        mainHandler.post {
            Toast.makeText(context, message, Toast.LENGTH_SHORT).show()
        }
    }
}
