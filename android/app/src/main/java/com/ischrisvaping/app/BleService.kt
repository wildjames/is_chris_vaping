package com.ischrisvaping.app

import android.annotation.SuppressLint
import android.app.*
import android.bluetooth.*
import android.bluetooth.le.BluetoothLeScanner
import android.bluetooth.le.ScanCallback
import android.bluetooth.le.ScanFilter
import android.bluetooth.le.ScanResult
import android.bluetooth.le.ScanSettings
import android.content.Intent
import android.os.Binder
import android.os.Build
import android.os.Handler
import android.os.IBinder
import android.os.Looper
import android.os.ParcelUuid
import android.util.Log
import android.widget.Toast
import java.io.OutputStreamWriter
import java.net.HttpURLConnection
import java.net.URL
import java.util.UUID
import java.util.concurrent.Executors

class BleService : Service() {

    companion object {
        private const val TAG = "BleService"
        private const val NOTIFICATION_ID = 1
        private const val CHANNEL_ID = "ble_service_channel"

        val SERVICE_UUID: UUID = UUID.fromString("189a9192-f68f-4ac4-962e-d70e7c3755a0")
        val CHARACTERISTIC_UUID: UUID = UUID.fromString("5cf4a205-84e1-42ad-ac23-e5adc776a992")
        val CCCD_UUID: UUID = UUID.fromString("00002902-0000-1000-8000-00805f9b34fb")

        const val ACTION_DATA_UPDATED = "com.ischrisvaping.app.DATA_UPDATED"
        const val ACTION_STATUS_UPDATED = "com.ischrisvaping.app.STATUS_UPDATED"
        const val EXTRA_DATA = "data"
        const val EXTRA_STATUS = "status"
    }

    private var bluetoothAdapter: BluetoothAdapter? = null
    private var bluetoothLeScanner: BluetoothLeScanner? = null
    private var bluetoothGatt: BluetoothGatt? = null
    private var isScanning = false

    private val httpExecutor = Executors.newSingleThreadExecutor()

    private var serverUrl: String = ""
    private var authToken: String = ""

    var currentData: String = ""
        private set
    var currentStatus: String = "Idle"
        private set
    var coilAActive: Boolean = false
        private set
    var coilBActive: Boolean = false
        private set

    private val binder = LocalBinder()

    inner class LocalBinder : Binder() {
        fun getService(): BleService = this@BleService
    }

    override fun onBind(intent: Intent?): IBinder = binder

    override fun onCreate() {
        super.onCreate()
        createNotificationChannel()

        val prefs = getSharedPreferences("vape_config", MODE_PRIVATE)
        serverUrl = prefs.getString("server_url", "") ?: ""
        authToken = prefs.getString("auth_token", "") ?: ""

        val bluetoothManager = getSystemService(BLUETOOTH_SERVICE) as BluetoothManager
        bluetoothAdapter = bluetoothManager.adapter
        bluetoothLeScanner = bluetoothAdapter?.bluetoothLeScanner
    }

    override fun onStartCommand(intent: Intent?, flags: Int, startId: Int): Int {
        startForeground(NOTIFICATION_ID, buildNotification("Searching for device..."))
        startScan()
        return START_STICKY
    }

    private fun createNotificationChannel() {
        val channel = NotificationChannel(
            CHANNEL_ID,
            "BLE Connection",
            NotificationManager.IMPORTANCE_LOW
        ).apply {
            description = "Maintains BLE connection to ESP32"
        }
        val notificationManager = getSystemService(NotificationManager::class.java)
        notificationManager.createNotificationChannel(channel)
    }

    private fun buildNotification(content: String): Notification {
        val pendingIntent = PendingIntent.getActivity(
            this, 0,
            Intent(this, MainActivity::class.java),
            PendingIntent.FLAG_IMMUTABLE
        )

        return Notification.Builder(this, CHANNEL_ID)
            .setContentTitle("IsChrisVaping")
            .setContentText(content)
            .setSmallIcon(android.R.drawable.stat_sys_data_bluetooth)
            .setContentIntent(pendingIntent)
            .setOngoing(true)
            .build()
    }

    private fun updateNotification(content: String) {
        val notificationManager = getSystemService(NotificationManager::class.java)
        notificationManager.notify(NOTIFICATION_ID, buildNotification(content))
    }

    @SuppressLint("MissingPermission")
    fun startScan() {
        if (isScanning) return

        val filter = ScanFilter.Builder()
            .setServiceUuid(ParcelUuid(SERVICE_UUID))
            .build()

        val settings = ScanSettings.Builder()
            .setScanMode(ScanSettings.SCAN_MODE_LOW_POWER)
            .build()

        updateStatus("Scanning for vape...")
        bluetoothLeScanner?.startScan(listOf(filter), settings, scanCallback)
        isScanning = true
    }

    @SuppressLint("MissingPermission")
    private fun stopScan() {
        if (!isScanning) return
        bluetoothLeScanner?.stopScan(scanCallback)
        isScanning = false
    }

    private val scanCallback = object : ScanCallback() {
        @SuppressLint("MissingPermission")
        override fun onScanResult(callbackType: Int, result: ScanResult) {
            Log.d(TAG, "Found device: ${result.device.name} - ${result.device.address}")
            stopScan()
            connectToDevice(result.device)
        }

        override fun onScanFailed(errorCode: Int) {
            Log.e(TAG, "Scan failed: $errorCode")
            updateStatus("Scan failed (error $errorCode)")
            isScanning = false
        }
    }

    @SuppressLint("MissingPermission")
    private fun connectToDevice(device: BluetoothDevice) {
        updateStatus("Connecting to ${device.name ?: device.address}...")
        bluetoothGatt = device.connectGatt(this, true, gattCallback, BluetoothDevice.TRANSPORT_LE)
    }

    private val gattCallback = object : BluetoothGattCallback() {
        @SuppressLint("MissingPermission")
        override fun onConnectionStateChange(gatt: BluetoothGatt, status: Int, newState: Int) {
            when (newState) {
                BluetoothProfile.STATE_CONNECTED -> {
                    Log.d(TAG, "Connected to GATT server")
                    updateStatus("Connected. Discovering services...")
                    gatt.discoverServices()
                }
                BluetoothProfile.STATE_DISCONNECTED -> {
                    Log.d(TAG, "Disconnected from GATT server")
                    updateStatus("Disconnected - reconnecting...")
                    bluetoothGatt?.close()
                    bluetoothGatt = null
                    startScan()
                }
            }
        }

        @SuppressLint("MissingPermission")
        override fun onServicesDiscovered(gatt: BluetoothGatt, status: Int) {
            if (status != BluetoothGatt.GATT_SUCCESS) {
                updateStatus("Service discovery failed")
                return
            }

            val service = gatt.getService(SERVICE_UUID)
            if (service == null) {
                updateStatus("Service not found")
                return
            }

            val characteristic = service.getCharacteristic(CHARACTERISTIC_UUID)
            if (characteristic == null) {
                updateStatus("Characteristic not found")
                return
            }

            gatt.setCharacteristicNotification(characteristic, true)
            val descriptor = characteristic.getDescriptor(CCCD_UUID)
            if (descriptor != null) {
                gatt.writeDescriptor(descriptor, BluetoothGattDescriptor.ENABLE_NOTIFICATION_VALUE)
            }

            gatt.readCharacteristic(characteristic)
            updateStatus("Connected - listening for data")
        }

        override fun onCharacteristicRead(
            gatt: BluetoothGatt, characteristic: BluetoothGattCharacteristic, value: ByteArray, status: Int
        ) {
            if (status == BluetoothGatt.GATT_SUCCESS) {
                val text = value.toString(Charsets.UTF_8)
                Log.d(TAG, "Read value: $text")
                updateData(text)
            }
        }

        override fun onCharacteristicChanged(
            gatt: BluetoothGatt, characteristic: BluetoothGattCharacteristic, value: ByteArray
        ) {
            val text = value.toString(Charsets.UTF_8)
            Log.d(TAG, "Notification: $text")
            updateData(text)
        }
    }

    private fun updateStatus(message: String) {
        Log.d(TAG, "Status: $message")
        currentStatus = message
        updateNotification(message)
        sendBroadcast(Intent(ACTION_STATUS_UPDATED).apply {
            setPackage(packageName)
            putExtra(EXTRA_STATUS, message)
        })
    }

    private fun updateData(data: String) {
        currentData = data
        parseCoilMessage(data)
        updateNotification(getHumanReadableStatus())
        sendBroadcast(Intent(ACTION_DATA_UPDATED).apply {
            setPackage(packageName)
            putExtra(EXTRA_DATA, data)
        })
    }

    private fun parseCoilMessage(message: String) {
        when (message) {
            "COIL_A:STARTED" -> {
                coilAActive = true
                Log.d(TAG, "Coil A started - vaping detected")
                postToServer("coil_a", "started")
            }
            "COIL_A:STOPPED" -> {
                coilAActive = false
                Log.d(TAG, "Coil A stopped")
                postToServer("coil_a", "stopped")
            }
            "COIL_B:STARTED" -> {
                coilBActive = true
                Log.d(TAG, "Coil B started - vaping detected")
                postToServer("coil_b", "started")
            }
            "COIL_B:STOPPED" -> {
                coilBActive = false
                Log.d(TAG, "Coil B stopped")
                postToServer("coil_b", "stopped")
            }
            else -> Log.d(TAG, "Unknown message: $message")
        }
    }

    private fun getHumanReadableStatus(): String {
        return when {
            coilAActive && coilBActive -> "Chris is vaping (both coils)"
            coilAActive -> "Chris is vaping (coil A)"
            coilBActive -> "Chris is vaping (coil B)"
            else -> "Not vaping"
        }
    }

    private fun postToServer(coil: String, event: String) {
        httpExecutor.execute {
            try {
                if (serverUrl.isBlank() || authToken.isBlank()) {
                    Log.w(TAG, "Server URL or auth token not configured, skipping post")
                    return@execute
                }
                val url = URL(serverUrl)
                val connection = url.openConnection() as HttpURLConnection
                connection.requestMethod = "POST"
                connection.setRequestProperty("Content-Type", "application/json")
                connection.setRequestProperty("Authorization", "Bearer $authToken")
                connection.doOutput = true
                connection.connectTimeout = 10000
                connection.readTimeout = 10000

                val json = """{"coil":"$coil","event":"$event","timestamp":${System.currentTimeMillis()}}"""

                OutputStreamWriter(connection.outputStream).use { writer ->
                    writer.write(json)
                    writer.flush()
                }

                val responseCode = connection.responseCode
                Log.d(TAG, "Server response: $responseCode for $coil:$event")
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

    private fun showToast(message: String) {
        Handler(Looper.getMainLooper()).post {
            Toast.makeText(this@BleService, message, Toast.LENGTH_SHORT).show()
        }
    }

    @SuppressLint("MissingPermission")
    override fun onDestroy() {
        super.onDestroy()
        stopScan()
        bluetoothGatt?.disconnect()
        bluetoothGatt?.close()
        httpExecutor.shutdown()
    }
}
