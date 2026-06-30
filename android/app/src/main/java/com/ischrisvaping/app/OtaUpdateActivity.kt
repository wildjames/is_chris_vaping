package com.ischrisvaping.app

import android.annotation.SuppressLint
import android.bluetooth.*
import android.content.ComponentName
import android.content.Intent
import android.content.ServiceConnection
import android.os.Bundle
import android.os.Handler
import android.os.IBinder
import android.os.Looper
import android.util.Log
import android.widget.Button
import android.widget.ProgressBar
import android.widget.TextView
import androidx.appcompat.app.AppCompatActivity
import org.json.JSONObject
import java.io.ByteArrayOutputStream
import java.net.HttpURLConnection
import java.net.URL
import java.util.UUID
import java.util.concurrent.Executors
import java.util.concurrent.LinkedBlockingQueue
import java.util.concurrent.Semaphore
import java.util.concurrent.TimeUnit

class OtaUpdateActivity : AppCompatActivity() {

    companion object {
        private const val TAG = "OtaUpdate"

        val OTA_SERVICE_UUID: UUID = UUID.fromString("fb1e4001-54ae-4a28-9f74-dfccb248601d")
        val OTA_CONTROL_UUID: UUID = UUID.fromString("fb1e4002-54ae-4a28-9f74-dfccb248601d")
        val OTA_DATA_UUID: UUID = UUID.fromString("fb1e4003-54ae-4a28-9f74-dfccb248601d")
        val OTA_VERSION_UUID: UUID = UUID.fromString("fb1e4004-54ae-4a28-9f74-dfccb248601d")
        val CCCD_UUID: UUID = UUID.fromString("00002902-0000-1000-8000-00805f9b34fb")

        private const val OTA_CMD_BEGIN: Byte = 0x01
        private const val OTA_CMD_END: Byte = 0x02
        private const val OTA_CMD_ABORT: Byte = 0x03

        private const val OTA_RSP_READY: Byte = 0x10
        private const val OTA_RSP_OK: Byte = 0x11
        private const val OTA_RSP_ERROR: Byte = 0x12
        private const val OTA_RSP_ACK: Byte = 0x13

        private const val CHUNK_SIZE = 509 // MTU 512 - 3 bytes ATT overhead
        private const val ACK_INTERVAL = 50 // Must match ESP32 OTA_ACK_INTERVAL
    }

    private lateinit var statusText: TextView
    private lateinit var versionText: TextView
    private lateinit var serverVersionText: TextView
    private lateinit var rssiText: TextView
    private lateinit var progressBar: ProgressBar
    private lateinit var progressText: TextView
    private lateinit var startUpdateButton: Button

    private var bleService: BleService? = null
    private var serviceBound = false
    private var bluetoothGatt: BluetoothGatt? = null
    private var otaControlChar: BluetoothGattCharacteristic? = null
    private var otaDataChar: BluetoothGattCharacteristic? = null
    private var otaVersionChar: BluetoothGattCharacteristic? = null

    private var firmwareData: ByteArray? = null
    private var isUpdating = false
    private var mtuSize = 23
    private var deviceFirmwareVersion: String? = null
    private var serverFirmwareVersion: String? = null
    private var awaitingReconnect = false
    private var targetDeviceAddress: String? = null

    private val mainHandler = Handler(Looper.getMainLooper())
    private val responseQueue = LinkedBlockingQueue<ByteArray>()
    private val writeSemaphore = Semaphore(0)
    @Volatile private var lastWriteStatus: Int = BluetoothGatt.GATT_SUCCESS
    private val executor = Executors.newSingleThreadExecutor()

    private val rssiRunnable = object : Runnable {
        @SuppressLint("MissingPermission")
        override fun run() {
            bluetoothGatt?.readRemoteRssi()
            mainHandler.postDelayed(this, 2000)
        }
    }

    private val serviceConnection = object : ServiceConnection {
        override fun onServiceConnected(name: ComponentName?, service: IBinder?) {
            val binder = service as BleService.LocalBinder
            bleService = binder.getService()
            serviceBound = true
            bleService?.gattEventListener = gattEventListener
            onBleServiceConnected()
        }

        override fun onServiceDisconnected(name: ComponentName?) {
            bleService?.gattEventListener = null
            bleService = null
            serviceBound = false
        }
    }

    private val gattEventListener = object : GattConnectionManager.GattEventListener {
        override fun onCharacteristicChanged(characteristic: BluetoothGattCharacteristic, value: ByteArray) {
            if (characteristic.uuid == OTA_CONTROL_UUID) {
                responseQueue.offer(value)
            }
        }

        override fun onCharacteristicRead(characteristic: BluetoothGattCharacteristic, value: ByteArray, status: Int) {
            if (characteristic.uuid == OTA_VERSION_UUID && status == BluetoothGatt.GATT_SUCCESS) {
                val version = value.toString(Charsets.UTF_8)
                deviceFirmwareVersion = version
                mainHandler.post {
                    versionText.text = "Device firmware: v$version"
                    if (awaitingReconnect) {
                        awaitingReconnect = false
                        if (version == serverFirmwareVersion) {
                            updateStatus("Update confirmed! Now running v$version")
                        } else {
                            updateStatus("Device reconnected with v$version (expected v$serverFirmwareVersion)")
                        }
                        startUpdateButton.isEnabled = false
                    } else {
                        checkUpdateAvailable()
                    }
                }
            }
        }

        override fun onCharacteristicWrite(characteristic: BluetoothGattCharacteristic, status: Int) {
            lastWriteStatus = status
            writeSemaphore.release()
        }

        @SuppressLint("MissingPermission")
        override fun onDescriptorWrite(descriptor: BluetoothGattDescriptor, status: Int) {
            // Descriptor write completed - now safe to read the version characteristic
            if (otaVersionChar != null) {
                bluetoothGatt?.readCharacteristic(otaVersionChar)
            }
        }

        @SuppressLint("MissingPermission")
        override fun onMtuChanged(mtu: Int) {
            mtuSize = mtu
            Log.d(TAG, "MTU changed to $mtu")
            // MTU negotiation done - now safe to do the descriptor write
            mainHandler.post { discoverOtaService() }
        }

        override fun onReadRemoteRssi(rssi: Int) {
            mainHandler.post { updateRssiDisplay(rssi) }
        }
    }

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        setContentView(R.layout.activity_ota_update)

        statusText = findViewById(R.id.otaStatusText)
        versionText = findViewById(R.id.otaVersionText)
        serverVersionText = findViewById(R.id.otaServerVersionText)
        rssiText = findViewById(R.id.otaRssiText)
        progressBar = findViewById(R.id.otaProgressBar)
        progressText = findViewById(R.id.otaProgressText)
        startUpdateButton = findViewById(R.id.startUpdateButton)

        startUpdateButton.isEnabled = false

        startUpdateButton.setOnClickListener {
            startOtaUpdate()
        }

        targetDeviceAddress = intent.getStringExtra("device_address")

        // Bind to the existing BLE service
        updateStatus("Connecting to BLE service...")
        bindService(Intent(this, BleService::class.java), serviceConnection, BIND_AUTO_CREATE)

        fetchServerFirmwareInfo()
    }

    @SuppressLint("MissingPermission")
    private fun onBleServiceConnected() {
        // Select the target device for OTA event forwarding
        val connectedDevice = if (targetDeviceAddress != null) {
            bleService?.devices?.get(targetDeviceAddress)?.takeIf { it.connected }
        } else {
            bleService?.devices?.values?.firstOrNull { it.connected }
        }
        if (connectedDevice == null) {
            updateStatus("Device not connected - go back and wait for connection")
            return
        }
        bleService?.selectedDeviceAddress = connectedDevice.address

        val gatt = connectedDevice.gatt
        if (gatt == null) {
            updateStatus("Device not connected - go back and wait for connection")
            return
        }

        bluetoothGatt = gatt

        // Request high priority connection interval (7.5-15ms) for faster transfers
        gatt.requestConnectionPriority(BluetoothGatt.CONNECTION_PRIORITY_HIGH)

        // Request higher MTU for faster transfers
        // The rest of setup happens in onMtuChanged callback
        gatt.requestMtu(512)
    }

    @SuppressLint("MissingPermission")
    private fun discoverOtaService() {
        val gatt = bluetoothGatt ?: return

        // Discover OTA service from the existing connection
        val otaService = gatt.getService(OTA_SERVICE_UUID)
        if (otaService == null) {
            updateStatus("OTA service not found - firmware may not support OTA")
            return
        }

        otaControlChar = otaService.getCharacteristic(OTA_CONTROL_UUID)
        otaDataChar = otaService.getCharacteristic(OTA_DATA_UUID)
        otaVersionChar = otaService.getCharacteristic(OTA_VERSION_UUID)

        // Enable notifications on control characteristic
        gatt.setCharacteristicNotification(otaControlChar, true)
        val descriptor = otaControlChar?.getDescriptor(CCCD_UUID)
        if (descriptor != null) {
            // Version read will be triggered in onDescriptorWrite callback
            gatt.writeDescriptor(descriptor, BluetoothGattDescriptor.ENABLE_NOTIFICATION_VALUE)
        } else {
            // No descriptor to write, read version directly
            if (otaVersionChar != null) {
                gatt.readCharacteristic(otaVersionChar)
            }
        }

        updateStatus("Connected to device")
        checkUpdateAvailable()

        // Start periodic RSSI reading
        mainHandler.post(rssiRunnable)
    }

    private fun getServerBaseUrl(): String {
        val prefs = getSharedPreferences("vape_config", MODE_PRIVATE)
        val url = prefs.getString("server_url", "") ?: ""
        // Strip the path (e.g. /vape-update) to get the base URL
        return if (url.isNotBlank()) {
            val parsed = URL(url)
            "${parsed.protocol}://${parsed.host}${if (parsed.port != -1 && parsed.port != parsed.defaultPort) ":${parsed.port}" else ""}"
        } else ""
    }

    private fun fetchServerFirmwareInfo() {
        executor.execute {
            try {
                val baseUrl = getServerBaseUrl()
                if (baseUrl.isBlank()) {
                    mainHandler.post { serverVersionText.text = "Server: not configured" }
                    return@execute
                }

                val url = URL("$baseUrl/firmware/latest")
                val connection = url.openConnection() as HttpURLConnection
                connection.requestMethod = "GET"
                connection.connectTimeout = 10000
                connection.readTimeout = 10000

                val responseCode = connection.responseCode
                if (responseCode == 200) {
                    val body = connection.inputStream.bufferedReader().readText()
                    val json = JSONObject(body)
                    serverFirmwareVersion = json.getString("version")
                    mainHandler.post {
                        serverVersionText.text = "Server firmware: v$serverFirmwareVersion"
                        checkUpdateAvailable()
                    }
                } else if (responseCode == 404) {
                    mainHandler.post { serverVersionText.text = "Server: no firmware uploaded" }
                } else {
                    mainHandler.post { serverVersionText.text = "Server: error ($responseCode)" }
                }
                connection.disconnect()
            } catch (e: Exception) {
                Log.e(TAG, "Failed to fetch firmware info", e)
                mainHandler.post { serverVersionText.text = "Server: unreachable" }
            }
        }
    }

    private fun downloadFirmware(onComplete: (ByteArray?) -> Unit) {
        executor.execute {
            try {
                val baseUrl = getServerBaseUrl()
                val url = URL("$baseUrl/firmware/download")
                val connection = url.openConnection() as HttpURLConnection
                connection.requestMethod = "GET"
                connection.connectTimeout = 15000
                connection.readTimeout = 30000

                if (connection.responseCode == 200) {
                    val buffer = ByteArrayOutputStream()
                    val data = ByteArray(8192)
                    var bytesRead: Int
                    connection.inputStream.use { input ->
                        while (input.read(data).also { bytesRead = it } != -1) {
                            buffer.write(data, 0, bytesRead)
                        }
                    }
                    val firmware = buffer.toByteArray()
                    Log.d(TAG, "Downloaded firmware: ${firmware.size} bytes")
                    mainHandler.post { onComplete(firmware) }
                } else {
                    Log.e(TAG, "Download failed: ${connection.responseCode}")
                    mainHandler.post { onComplete(null) }
                }
                connection.disconnect()
            } catch (e: Exception) {
                Log.e(TAG, "Download error", e)
                mainHandler.post { onComplete(null) }
            }
        }
    }

    private fun checkUpdateAvailable() {
        val deviceVer = deviceFirmwareVersion
        val serverVer = serverFirmwareVersion
        if (deviceVer != null && serverVer != null && otaControlChar != null) {
            if (deviceVer != serverVer) {
                startUpdateButton.isEnabled = true
                updateStatus("Update available: v$deviceVer → v$serverVer")
            } else {
                updateStatus("Firmware is up to date (v$deviceVer)")
                startUpdateButton.isEnabled = false
            }
        }
    }

    private fun startOtaUpdate() {
        startUpdateButton.isEnabled = false
        updateStatus("Downloading firmware from server...")
        progressBar.progress = 0
        progressText.text = "Downloading..."

        downloadFirmware { data ->
            if (data == null) {
                updateStatus("Failed to download firmware")
                startUpdateButton.isEnabled = true
                return@downloadFirmware
            }
            firmwareData = data
            updateStatus("Downloaded ${data.size} bytes. Starting BLE transfer...")
            performBleUpdate()
        }
    }

    private fun performBleUpdate() {
        val data = firmwareData ?: return
        val gatt = bluetoothGatt ?: return
        val controlChar = otaControlChar ?: return
        val dataChar = otaDataChar ?: return

        isUpdating = true

        executor.execute {
            val maxAttempts = 3
            var lastError: Exception? = null

            for (attempt in 1..maxAttempts) {
                try {
                    if (attempt > 1) {
                        Log.w(TAG, "Retrying OTA transfer (attempt $attempt/$maxAttempts)")
                        mainHandler.post {
                            updateStatus("Retry $attempt/$maxAttempts...")
                            progressBar.progress = 0
                        }
                        // Brief delay before retry to let ESP32 settle
                        Thread.sleep(2000)
                    }
                    transferFirmware(gatt, controlChar, dataChar, data)
                    lastError = null
                    break
                } catch (e: Exception) {
                    Log.e(TAG, "OTA attempt $attempt failed", e)
                    lastError = e
                    // Send ABORT so ESP32 resets OTA state for retry
                    try {
                        writeSemaphore.drainPermits()
                        gatt.writeCharacteristic(controlChar, byteArrayOf(OTA_CMD_ABORT), BluetoothGattCharacteristic.WRITE_TYPE_DEFAULT)
                        writeSemaphore.tryAcquire(3, TimeUnit.SECONDS)
                    } catch (_: Exception) { }
                    responseQueue.clear()
                }
            }

            if (lastError != null) {
                mainHandler.post {
                    updateStatus("Update failed after $maxAttempts attempts: ${lastError.message}")
                    isUpdating = false
                    startUpdateButton.isEnabled = true
                }
            }
        }
    }

    @SuppressLint("MissingPermission")
    private fun transferFirmware(
        gatt: BluetoothGatt,
        controlChar: BluetoothGattCharacteristic,
        dataChar: BluetoothGattCharacteristic,
        firmware: ByteArray
    ) {
        responseQueue.clear()

        // Send BEGIN command with file size (little-endian)
        val size = firmware.size
        val beginCmd = byteArrayOf(
            OTA_CMD_BEGIN,
            (size and 0xFF).toByte(),
            ((size shr 8) and 0xFF).toByte(),
            ((size shr 16) and 0xFF).toByte(),
            ((size shr 24) and 0xFF).toByte()
        )

        gatt.writeCharacteristic(controlChar, beginCmd, BluetoothGattCharacteristic.WRITE_TYPE_DEFAULT)

        // Wait for READY response
        val readyResponse = responseQueue.poll(10, TimeUnit.SECONDS)
        if (readyResponse == null || readyResponse[0] != OTA_RSP_READY) {
            val errorMsg = if (readyResponse != null && readyResponse[0] == OTA_RSP_ERROR) {
                "Device rejected update (error code: ${readyResponse.getOrNull(1) ?: "unknown"})"
            } else {
                "No response from device"
            }
            throw Exception(errorMsg)
        }

        mainHandler.post { updateStatus("Transferring firmware...") }

        // Send firmware data in chunks with flow control
        val chunkSize = minOf(CHUNK_SIZE, mtuSize - 3)
        var offset = 0
        var chunksSent = 0

        val maxRetries = 10

        while (offset < size) {
            val end = minOf(offset + chunkSize, size)
            val chunk = firmware.copyOfRange(offset, end)

            var written = false
            for (attempt in 1..maxRetries) {
                writeSemaphore.drainPermits()
                lastWriteStatus = BluetoothGatt.GATT_SUCCESS
                gatt.writeCharacteristic(dataChar, chunk, BluetoothGattCharacteristic.WRITE_TYPE_NO_RESPONSE)

                // Wait for write completion callback before sending next chunk
                if (!writeSemaphore.tryAcquire(5, TimeUnit.SECONDS)) {
                    throw Exception("BLE write timed out at offset $offset")
                }

                if (lastWriteStatus == BluetoothGatt.GATT_SUCCESS) {
                    written = true
                    break
                }
                Log.w(TAG, "BLE write failed (status=$lastWriteStatus) at offset $offset, attempt $attempt/$maxRetries")
            }

            if (!written) {
                throw Exception("BLE write failed after $maxRetries retries at offset $offset (status=$lastWriteStatus)")
            }

            offset = end
            chunksSent++

            // Update progress
            val progress = (offset * 100) / size
            mainHandler.post {
                progressBar.progress = progress
                progressText.text = "${offset / 1024}KB / ${size / 1024}KB ($progress%)"
            }

            // Every ACK_INTERVAL chunks, wait for ACK from ESP32 with byte count verification
            if (chunksSent % ACK_INTERVAL == 0) {
                val ack = responseQueue.poll(10, TimeUnit.SECONDS)
                if (ack == null) {
                    throw Exception("No ACK from device after $chunksSent chunks (offset $offset)")
                }
                if (ack[0] == OTA_RSP_ERROR) {
                    throw Exception("Device reported error during transfer (code: ${ack.getOrNull(1) ?: "unknown"})")
                }
                if (ack[0] == OTA_RSP_ACK && ack.size >= 5) {
                    val deviceReceived = (ack[1].toInt() and 0xFF) or
                            ((ack[2].toInt() and 0xFF) shl 8) or
                            ((ack[3].toInt() and 0xFF) shl 16) or
                            ((ack[4].toInt() and 0xFF) shl 24)
                    if (deviceReceived != offset) {
                        throw Exception("Dropped packets: sent $offset bytes but device received $deviceReceived")
                    }
                    Log.d(TAG, "ACK verified: $deviceReceived bytes received by device")
                }
            } else {
                // Non-blocking check for error notifications between ACK intervals
                val notification = responseQueue.poll()
                if (notification != null && notification[0] == OTA_RSP_ERROR) {
                    throw Exception("Device reported error during transfer (code: ${notification.getOrNull(1) ?: "unknown"})")
                }
            }
        }

        mainHandler.post { updateStatus("Transfer complete, verifying...") }

        // Drain any stale notifications before sending END
        while (responseQueue.poll() != null) { /* discard */ }

        // Send END command - device will reboot on success, which may disconnect BLE
        // before we get a response, so treat connection failures here as likely success
        try {
            writeSemaphore.drainPermits()
            gatt.writeCharacteristic(controlChar, byteArrayOf(OTA_CMD_END), BluetoothGattCharacteristic.WRITE_TYPE_DEFAULT)
            if (!writeSemaphore.tryAcquire(5, TimeUnit.SECONDS)) {
                Log.w(TAG, "END command write timed out - device likely rebooted")
                mainHandler.post {
                    progressBar.progress = 100
                    progressText.text = "Complete!"
                }
                isUpdating = false
                waitForReconnect()
                return
            }

            // Wait for OK response (device will reboot after this)
            val endResponse = responseQueue.poll(10, TimeUnit.SECONDS)
            if (endResponse != null && endResponse[0] == OTA_RSP_OK) {
                mainHandler.post {
                    progressBar.progress = 100
                    progressText.text = "Complete!"
                }
                isUpdating = false
                waitForReconnect()
            } else if (endResponse != null && endResponse[0] == OTA_RSP_ERROR) {
                throw Exception("Verification failed on device (code: ${endResponse.getOrNull(1) ?: "unknown"})")
            } else {
                // No response - device likely already rebooted (success)
                Log.w(TAG, "No END response - device likely rebooted")
                mainHandler.post {
                    progressBar.progress = 100
                    progressText.text = "Complete!"
                }
                isUpdating = false
                waitForReconnect()
            }
        } catch (e: Exception) {
            // If the exception is from the END phase and not an explicit device error,
            // the device most likely rebooted after a successful update
            if (e.message?.contains("Verification failed") == true) {
                throw e
            }
            Log.w(TAG, "END phase failed (device likely rebooted): ${e.message}")
            mainHandler.post {
                progressBar.progress = 100
                progressText.text = "Complete!"
            }
            isUpdating = false
            waitForReconnect()
        }
    }

    private fun updateRssiDisplay(rssi: Int) {
        val label = when {
            rssi >= -50 -> "Excellent"
            rssi >= -60 -> "Good"
            rssi >= -70 -> "Fair"
            rssi >= -80 -> "Weak"
            else -> "Very weak"
        }
        rssiText.text = "Signal: $rssi dBm ($label)"
    }

    @SuppressLint("MissingPermission")
    private fun waitForReconnect() {
        awaitingReconnect = true
        mainHandler.removeCallbacks(rssiRunnable)
        mainHandler.post {
            rssiText.text = ""
            updateStatus("Waiting for device to reboot...")
        }

        executor.execute {
            val maxWaitMs = 30000L
            val pollIntervalMs = 500L
            val startTime = System.currentTimeMillis()

            // Wait for disconnect first
            while (System.currentTimeMillis() - startTime < maxWaitMs) {
                val device = bleService?.devices?.values?.firstOrNull {
                    it.address == (targetDeviceAddress ?: bleService?.selectedDeviceAddress)
                }
                if (device == null || !device.connected) break
                Thread.sleep(pollIntervalMs)
            }

            mainHandler.post { updateStatus("Device rebooting, waiting for reconnection...") }

            // Now wait for reconnect
            while (System.currentTimeMillis() - startTime < maxWaitMs) {
                val device = bleService?.devices?.values?.firstOrNull {
                    it.address == (targetDeviceAddress ?: bleService?.selectedDeviceAddress) && it.connected
                }
                if (device != null && device.gatt != null) {
                    bluetoothGatt = device.gatt
                    mainHandler.post {
                        updateStatus("Reconnected! Reading firmware version...")
                        bluetoothGatt?.requestMtu(512)
                    }
                    return@execute
                }
                Thread.sleep(pollIntervalMs)
            }

            // Timeout
            mainHandler.post {
                awaitingReconnect = false
                updateStatus("Update likely successful but device didn't reconnect in time")
            }
        }
    }

    private fun updateStatus(message: String) {
        statusText.text = message
        Log.d(TAG, message)
    }

    @SuppressLint("MissingPermission")
    override fun onDestroy() {
        super.onDestroy()
        mainHandler.removeCallbacks(rssiRunnable)
        if (isUpdating) {
            val controlChar = otaControlChar
            if (controlChar != null && bluetoothGatt != null) {
                bluetoothGatt?.writeCharacteristic(
                    controlChar, byteArrayOf(OTA_CMD_ABORT), BluetoothGattCharacteristic.WRITE_TYPE_DEFAULT
                )
            }
        }
        bleService?.gattEventListener = null
        bleService?.selectedDeviceAddress = null
        if (serviceBound) {
            unbindService(serviceConnection)
            serviceBound = false
        }
        executor.shutdown()
    }
}
