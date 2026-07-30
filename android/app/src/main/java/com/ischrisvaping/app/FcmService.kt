package com.ischrisvaping.app

import android.app.Notification
import android.app.NotificationChannel
import android.app.NotificationManager
import android.app.PendingIntent
import android.content.Context
import android.content.Intent
import android.util.Log
import com.google.firebase.messaging.FirebaseMessagingService
import com.google.firebase.messaging.RemoteMessage
import org.json.JSONObject
import java.io.OutputStreamWriter
import java.net.HttpURLConnection
import java.net.URL
import java.util.concurrent.Executors

class FcmService : FirebaseMessagingService() {

    companion object {
        private const val TAG = "FcmService"
        const val ACHIEVEMENTS_CHANNEL_ID = "achievements_channel"
        private const val ACHIEVEMENTS_NOTIFICATION_ID_BASE = 1000
        private var notificationCounter = 0

        fun registerTokenForDevices(context: Context) {
            com.google.firebase.messaging.FirebaseMessaging.getInstance().token
                .addOnSuccessListener { token ->
                    Log.d(TAG, "FCM token obtained")
                    val prefs = context.getSharedPreferences("vape_config", Context.MODE_PRIVATE)
                    prefs.edit().putString("fcm_token", token).apply()
                    sendTokenToServer(context, token)
                }
                .addOnFailureListener { e ->
                    Log.e(TAG, "Failed to get FCM token: ${e.message}")
                }
        }

        private fun sendTokenToServer(context: Context, token: String) {
            val prefs = context.getSharedPreferences("vape_config", Context.MODE_PRIVATE)
            val serverUrl = prefs.getString("server_url", "") ?: ""
            val authToken = prefs.getString("auth_token", "") ?: ""
            if (serverUrl.isBlank() || authToken.isBlank()) return

            val devicePrefs = context.getSharedPreferences("vape_devices", Context.MODE_PRIVATE)
            val devicesJson = devicePrefs.getString("devices", null) ?: return

            Executors.newSingleThreadExecutor().execute {
                try {
                    val arr = org.json.JSONArray(devicesJson)
                    for (i in 0 until arr.length()) {
                        val deviceName = arr.getJSONObject(i).getString("name")
                        val url = URL("$serverUrl/push-token")
                        val connection = url.openConnection() as HttpURLConnection
                        try {
                            connection.requestMethod = "POST"
                            connection.setRequestProperty("Content-Type", "application/json")
                            connection.setRequestProperty("Authorization", "Bearer $authToken")
                            connection.doOutput = true
                            connection.connectTimeout = 10000
                            connection.readTimeout = 10000

                            val json = JSONObject().apply {
                                put("token", token)
                                put("device_name", deviceName)
                            }.toString()

                            OutputStreamWriter(connection.outputStream).use { it.write(json) }
                            val code = connection.responseCode
                            Log.d(TAG, "Registered push token for $deviceName: $code")
                        } finally {
                            connection.disconnect()
                        }
                    }
                } catch (e: Exception) {
                    Log.e(TAG, "Failed to register push token: ${e.message}")
                }
            }
        }
    }

    override fun onCreate() {
        super.onCreate()
        createAchievementsChannel()
    }

    override fun onNewToken(token: String) {
        super.onNewToken(token)
        Log.d(TAG, "New FCM token")
        val prefs = getSharedPreferences("vape_config", Context.MODE_PRIVATE)
        prefs.edit().putString("fcm_token", token).apply()
        sendTokenToServer(this, token)
    }

    override fun onMessageReceived(message: RemoteMessage) {
        super.onMessageReceived(message)

        val data = message.data
        if (data["type"] == "achievement") {
            showAchievementNotification(
                data["achievement_name"] ?: "Achievement Unlocked",
                message.notification?.body ?: data["device_name"] ?: "",
            )
        } else if (message.notification != null) {
            showAchievementNotification(
                message.notification!!.title ?: "WhoIsVaping",
                message.notification!!.body ?: "",
            )
        }
    }

    private fun showAchievementNotification(title: String, body: String) {
        val intent = PendingIntent.getActivity(
            this, 0,
            Intent(this, MainActivity::class.java),
            PendingIntent.FLAG_IMMUTABLE,
        )

        val notification = Notification.Builder(this, ACHIEVEMENTS_CHANNEL_ID)
            .setContentTitle(title)
            .setContentText(body)
            .setSmallIcon(android.R.drawable.star_big_on)
            .setContentIntent(intent)
            .setAutoCancel(true)
            .build()

        val nm = getSystemService(NotificationManager::class.java)
        nm.notify(ACHIEVEMENTS_NOTIFICATION_ID_BASE + (notificationCounter++ % 10), notification)
    }

    private fun createAchievementsChannel() {
        val channel = NotificationChannel(
            ACHIEVEMENTS_CHANNEL_ID,
            "Achievements",
            NotificationManager.IMPORTANCE_HIGH,
        ).apply {
            description = "Notifications for vape achievements"
        }
        val nm = getSystemService(NotificationManager::class.java)
        nm.createNotificationChannel(channel)
    }
}
