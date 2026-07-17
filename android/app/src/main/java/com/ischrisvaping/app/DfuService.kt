package com.ischrisvaping.app

import android.app.Activity
import android.app.NotificationChannel
import android.app.NotificationManager
import no.nordicsemi.android.dfu.DfuBaseService

/**
 * Thin wrapper required by the Nordic DFU library.
 * All OTA logic is handled by DfuBaseService; this class only declares
 * which Activity to open when the DFU progress notification is tapped.
 */
class DfuService : DfuBaseService() {

    override fun onCreate() {
        super.onCreate()
        // The DFU library posts foreground-service notifications on the "dfu" channel.
        // On Android 8+ this channel must exist before startForeground() is called.
        val channel = NotificationChannel(
            NOTIFICATION_CHANNEL_DFU,
            "Firmware Update",
            NotificationManager.IMPORTANCE_LOW
        ).apply {
            description = "Shows progress during firmware updates"
        }
        val manager = getSystemService(NotificationManager::class.java)
        manager.createNotificationChannel(channel)
    }

    override fun getNotificationTarget(): Class<out Activity> = OtaUpdateActivity::class.java
}
