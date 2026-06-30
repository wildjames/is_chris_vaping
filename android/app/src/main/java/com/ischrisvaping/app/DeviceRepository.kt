package com.ischrisvaping.app

import android.content.Context
import android.util.Log
import org.json.JSONArray
import org.json.JSONObject
import java.util.concurrent.ConcurrentHashMap

class DeviceRepository(private val context: Context) {

    companion object {
        private const val TAG = "DeviceRepository"
        private const val PREFS_NAME = "vape_devices"
        private const val KEY_DEVICES = "devices"
    }

    val devices = ConcurrentHashMap<String, VapeDevice>()

    fun load() {
        val prefs = context.getSharedPreferences(PREFS_NAME, Context.MODE_PRIVATE)
        val json = prefs.getString(KEY_DEVICES, null) ?: return
        try {
            val arr = JSONArray(json)
            for (i in 0 until arr.length()) {
                val obj = arr.getJSONObject(i)
                val address = obj.getString("address")
                val name = obj.getString("name")
                devices[address] = VapeDevice(address, name)
            }
            Log.d(TAG, "Loaded ${devices.size} saved devices")
        } catch (e: Exception) {
            Log.e(TAG, "Failed to load devices: ${e.message}")
        }
    }

    fun save() {
        val arr = JSONArray()
        for (device in devices.values) {
            val obj = JSONObject().apply {
                put("address", device.address)
                put("name", device.name)
            }
            arr.put(obj)
        }
        val prefs = context.getSharedPreferences(PREFS_NAME, Context.MODE_PRIVATE)
        prefs.edit().putString(KEY_DEVICES, arr.toString()).apply()
    }

    fun add(address: String, name: String): VapeDevice {
        val device = VapeDevice(address, name)
        devices[address] = device
        save()
        return device
    }

    fun remove(address: String): VapeDevice? {
        val device = devices.remove(address)
        save()
        return device
    }

    fun rename(address: String, newName: String): VapeDevice? {
        val device = devices[address] ?: return null
        device.name = newName
        save()
        return device
    }

    fun get(address: String): VapeDevice? = devices[address]

    fun hasDisconnectedDevices(): Boolean = devices.values.any { !it.connected }
}
