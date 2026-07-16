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
import android.net.Uri
import java.io.ByteArrayOutputStream
import java.io.File
import java.net.HttpURLConnection
import java.net.URL
import java.security.MessageDigest
import java.util.UUID
import java.util.concurrent.Executors
import no.nordicsemi.android.dfu.DfuProgressListenerAdapter
import no.nordicsemi.android.dfu.DfuServiceInitiator
import no.nordicsemi.android.dfu.DfuServiceListenerHelper

class OtaUpdateActivity : AppCompatActivity() {

    companion object {
        private const val TAG = "OtaUpdate"

        val OTA_SERVICE_UUID: UUID = UUID.fromString("fb1e4001-54ae-4a28-9f74-dfccb248601d")
        val OTA_VERSION_UUID: UUID = UUID.fromString("fb1e4004-54ae-4a28-9f74-dfccb248601d")
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
    private var otaVersionChar: BluetoothGattCharacteristic? = null

    private var firmwareData: ByteArray? = null
    private var isUpdating = false
    private var mtuSize = 23
    private var deviceFirmwareVersion: String? = null
    private var serverFirmwareVersion: String? = null
    private var serverFirmwareSha256: String? = null
    private var awaitingReconnect = false
    private var targetDeviceAddress: String? = null

    private val mainHandler = Handler(Looper.getMainLooper())

    private val dfuProgressListener = object : DfuProgressListenerAdapter() {
        override fun onEnablingDfuMode(deviceAddress: String) {
            mainHandler.post { updateStatus("Enabling DFU mode...") }
        }
        override fun onDfuProcessStarted(deviceAddress: String) {
            mainHandler.post { updateStatus("DFU transfer in progress...") }
        }
        override fun onFirmwareValidating(deviceAddress: String) {
            mainHandler.post { updateStatus("Validating firmware...") }
        }
        override fun onProgressChanged(deviceAddress: String, percent: Int, speed: Float, avgSpeed: Float, currentPart: Int, partsTotal: Int) {
            mainHandler.post {
                progressBar.progress = percent
                progressText.text = "$percent%"
            }
        }
        override fun onDfuCompleted(deviceAddress: String) {
            DfuServiceListenerHelper.unregisterProgressListener(this@OtaUpdateActivity, this)
            isUpdating = false
            mainHandler.post {
                progressBar.progress = 100
                progressText.text = "Complete!"
                waitForReconnect()
            }
        }
        override fun onError(deviceAddress: String, error: Int, errorType: Int, message: String) {
            DfuServiceListenerHelper.unregisterProgressListener(this@OtaUpdateActivity, this)
            isUpdating = false
            mainHandler.post {
                updateStatus("DFU error: $message (code $error)")
                startUpdateButton.isEnabled = true
            }
        }
    }
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
        }

        @SuppressLint("MissingPermission")
        override fun onDescriptorWrite(descriptor: BluetoothGattDescriptor, status: Int) {
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

        fetchServerFirmwareInfo()

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

        otaVersionChar = otaService.getCharacteristic(OTA_VERSION_UUID)

        if (otaVersionChar != null) {
            gatt.readCharacteristic(otaVersionChar)
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
            if (parsed.protocol != "https") {
                Log.e(TAG, "Server URL must use HTTPS")
                return ""
            }
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
                    serverFirmwareSha256 = json.optString("sha256", null)
                    // Log the server firmware version for debugging
                    Log.d(TAG, "Server firmware version: $serverFirmwareVersion")
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
                    val digest = MessageDigest.getInstance("SHA-256")
                    val buffer = ByteArrayOutputStream()
                    val data = ByteArray(8192)
                    var bytesRead: Int
                    connection.inputStream.use { input ->
                        while (input.read(data).also { bytesRead = it } != -1) {
                            buffer.write(data, 0, bytesRead)
                            digest.update(data, 0, bytesRead)
                        }
                    }
                    val firmware = buffer.toByteArray()
                    val downloadedHash = digest.digest().joinToString("") { "%02x".format(it) }
                    Log.d(TAG, "Downloaded firmware: ${firmware.size} bytes, SHA-256: $downloadedHash")

                    val expectedHash = serverFirmwareSha256
                    if (expectedHash != null && downloadedHash != expectedHash) {
                        Log.e(TAG, "Checksum mismatch! Expected: $expectedHash, got: $downloadedHash")
                        mainHandler.post { onComplete(null) }
                    } else {
                        mainHandler.post { onComplete(firmware) }
                    }
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
        if (deviceVer != null && serverVer != null) {
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
            updateStatus("Downloaded ${data.size} bytes. Starting Nordic DFU...")
            performNordicDfuUpdate(data)
        }
    }

    private fun performNordicDfuUpdate(data: ByteArray) {
        val address = targetDeviceAddress ?: bleService?.selectedDeviceAddress ?: run {
            updateStatus("No device address for DFU")
            startUpdateButton.isEnabled = true
            return
        }

        val tempFile = File(cacheDir, "firmware_dfu.zip")
        try {
            tempFile.writeBytes(data)
        } catch (e: Exception) {
            updateStatus("Failed to save firmware: ${e.message}")
            startUpdateButton.isEnabled = true
            return
        }

        isUpdating = true
        DfuServiceListenerHelper.registerProgressListener(this, dfuProgressListener)
        updateStatus("Starting Nordic DFU transfer...")

        // Disconnect the app's GATT connection before starting DFU.
        // The DFU library manages its own connection lifecycle and will fail
        // if another GATT client is already connected to the device.
        bleService?.disconnectDevice(address)
        bluetoothGatt = null

        DfuServiceInitiator(address)
            .setDeviceName("IsChrisVaping")
            .setZip(Uri.fromFile(tempFile))
            // The Adafruit nRF52 bootloader advertises on a different BLE
            // address (original +1). Tell the DFU library to scan for the
            // bootloader instead of connecting to the original address.
            .setForceScanningForNewAddressInLegacyDfu(true)
            .start(this, DfuService::class.java)
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
        DfuServiceListenerHelper.unregisterProgressListener(this, dfuProgressListener)
        bleService?.gattEventListener = null
        bleService?.selectedDeviceAddress = null
        if (serviceBound) {
            unbindService(serviceConnection)
            serviceBound = false
        }
        executor.shutdown()
    }
}
