package com.ischrisvaping.app

import android.app.Notification
import android.app.NotificationChannel
import android.app.NotificationManager
import android.app.PendingIntent
import android.content.Context
import android.content.Intent
import android.util.Log

class StatusNotifier(private val context: Context) {

    companion object {
        private const val TAG = "StatusNotifier"
        const val NOTIFICATION_ID = 1
        const val CHANNEL_ID = "ble_service_channel"

        const val ACTION_DATA_UPDATED = "com.ischrisvaping.app.DATA_UPDATED"
        const val ACTION_STATUS_UPDATED = "com.ischrisvaping.app.STATUS_UPDATED"
        const val ACTION_DEVICES_CHANGED = "com.ischrisvaping.app.DEVICES_CHANGED"
        const val ACTION_NOTIFICATION_DISMISSED = "com.ischrisvaping.app.NOTIFICATION_DISMISSED"
        const val EXTRA_DATA = "data"
        const val EXTRA_STATUS = "status"
        const val EXTRA_DEVICE_ADDRESS = "device_address"
    }

    var currentStatus: String = "Idle"
        private set
    var currentData: String = ""
        private set

    fun createNotificationChannel() {
        val channel = NotificationChannel(
            CHANNEL_ID,
            "BLE Connection",
            NotificationManager.IMPORTANCE_LOW
        ).apply {
            description = "Maintains BLE connection to vape device"
        }
        val notificationManager = context.getSystemService(NotificationManager::class.java)
        notificationManager.createNotificationChannel(channel)
    }

    fun buildNotification(content: String, ongoing: Boolean = true): Notification {
        val pendingIntent = PendingIntent.getActivity(
            context, 0,
            Intent(context, MainActivity::class.java),
            PendingIntent.FLAG_IMMUTABLE
        )

        val builder = Notification.Builder(context, CHANNEL_ID)
            .setContentTitle("WhoIsVaping")
            .setContentText(content)
            .setSmallIcon(android.R.drawable.stat_sys_data_bluetooth)
            .setContentIntent(pendingIntent)
            .setOngoing(ongoing)

        if (ongoing) {
            val deleteIntent = PendingIntent.getService(
                context, 0,
                Intent(context, BleService::class.java).apply {
                    action = ACTION_NOTIFICATION_DISMISSED
                },
                PendingIntent.FLAG_IMMUTABLE
            )
            builder.setDeleteIntent(deleteIntent)
        }

        return builder.build()
    }

    fun updateNotification(content: String, ongoing: Boolean = true) {
        val notificationManager = context.getSystemService(NotificationManager::class.java)
        notificationManager.notify(NOTIFICATION_ID, buildNotification(content, ongoing))
    }

    fun updateStatus(message: String) {
        Log.d(TAG, "Status: $message")
        currentStatus = message
        updateNotification(message)
        context.sendBroadcast(Intent(ACTION_STATUS_UPDATED).apply {
            setPackage(context.packageName)
            putExtra(EXTRA_STATUS, message)
        })
    }

    fun updateData(data: String, deviceAddress: String) {
        currentData = data
        context.sendBroadcast(Intent(ACTION_DATA_UPDATED).apply {
            setPackage(context.packageName)
            putExtra(EXTRA_DATA, data)
            putExtra(EXTRA_DEVICE_ADDRESS, deviceAddress)
        })
    }

    fun broadcastDevicesChanged() {
        context.sendBroadcast(Intent(ACTION_DEVICES_CHANGED).apply {
            setPackage(context.packageName)
        })
    }

    fun getOverallStatus(devices: Collection<VapeDevice>): String {
        val vapingDevices = devices.filter { it.coilAActive || it.coilBActive }
        val connectedDevices = devices.filter { it.connected }

        return when {
            vapingDevices.isNotEmpty() -> {
                val names = vapingDevices.joinToString(", ") { it.name }
                "Chuffing $names"
            }
            connectedDevices.isNotEmpty() -> {
                val names = connectedDevices.joinToString(", ") { it.name }
                "Connected to $names"
            }
            else -> "Scanning for vapes"
        }
    }
}
