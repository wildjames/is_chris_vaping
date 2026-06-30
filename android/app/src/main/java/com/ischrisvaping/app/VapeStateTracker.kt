package com.ischrisvaping.app

import android.util.Log
import java.util.concurrent.ConcurrentHashMap

class VapeStateTracker(private val serverClient: ServerClient) {

    companion object {
        private const val TAG = "VapeStateTracker"
        private const val DEDUP_WINDOW_MS = 2000L
    }

    private val lastPostedMessages = ConcurrentHashMap<String, Pair<String, Long>>()

    /**
     * Parse an incoming coil message and update device state.
     * Returns true if state changed (i.e. not a duplicate).
     */
    fun handleMessage(message: String, device: VapeDevice): Boolean {
        if (isDuplicate(device.address, message)) {
            Log.d(TAG, "Ignoring duplicate message from ${device.name}: $message")
            return false
        }

        when (message) {
            "COIL_A:STARTED" -> {
                device.coilAActive = true
                Log.d(TAG, "${device.name} Coil A started - vaping detected")
                serverClient.postVapeEvent("coil_a", "started", device.name)
            }
            "COIL_A:STOPPED" -> {
                device.coilAActive = false
                Log.d(TAG, "${device.name} Coil A stopped")
                serverClient.postVapeEvent("coil_a", "stopped", device.name)
            }
            "COIL_B:STARTED" -> {
                device.coilBActive = true
                Log.d(TAG, "${device.name} Coil B started - vaping detected")
                serverClient.postVapeEvent("coil_b", "started", device.name)
            }
            "COIL_B:STOPPED" -> {
                device.coilBActive = false
                Log.d(TAG, "${device.name} Coil B stopped")
                serverClient.postVapeEvent("coil_b", "stopped", device.name)
            }
            else -> {
                Log.d(TAG, "Unknown message from ${device.name}: $message")
                return false
            }
        }
        return true
    }

    /**
     * Called when a device disconnects - posts "stopped" for any active coils.
     */
    fun handleDisconnection(device: VapeDevice) {
        if (device.coilAActive) {
            device.coilAActive = false
            serverClient.postVapeEvent("coil_a", "stopped", device.name)
        }
        if (device.coilBActive) {
            device.coilBActive = false
            serverClient.postVapeEvent("coil_b", "stopped", device.name)
        }
    }

    private fun isDuplicate(address: String, message: String): Boolean {
        val now = System.currentTimeMillis()
        val key = "$address:$message"
        val last = lastPostedMessages[key]
        if (last != null && last.first == message && (now - last.second) < DEDUP_WINDOW_MS) {
            return true
        }
        lastPostedMessages[key] = Pair(message, now)
        return false
    }
}
