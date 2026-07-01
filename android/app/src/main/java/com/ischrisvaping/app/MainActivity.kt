package com.ischrisvaping.app

import android.Manifest
import android.annotation.SuppressLint
import android.content.*
import android.content.pm.PackageManager
import android.os.Build
import android.os.Bundle
import android.os.IBinder
import android.util.Log
import android.widget.Button
import android.widget.EditText
import android.widget.LinearLayout
import android.widget.TextView
import androidx.appcompat.app.AlertDialog
import androidx.appcompat.app.AppCompatActivity
import androidx.appcompat.widget.SwitchCompat
import androidx.core.app.ActivityCompat
import androidx.core.content.ContextCompat
import androidx.recyclerview.widget.LinearLayoutManager
import androidx.recyclerview.widget.RecyclerView
import android.view.LayoutInflater
import android.view.View
import android.view.ViewGroup
import org.json.JSONObject
import java.net.HttpURLConnection
import java.net.URL
import java.util.concurrent.Executors

class MainActivity : AppCompatActivity() {

    companion object {
        private const val TAG = "MainActivity"
        private const val REQUEST_PERMISSIONS = 1
    }

    private lateinit var statusText: TextView
    private lateinit var deviceList: RecyclerView
    private lateinit var deviceAdapter: DeviceAdapter

    private var bleService: BleService? = null
    private var serviceBound = false
    private val serverFirmwareVersions: MutableMap<String, String> = mutableMapOf()
    private val executor = Executors.newSingleThreadExecutor()
    private val versionPollHandler = android.os.Handler(android.os.Looper.getMainLooper())
    private val versionPollRunnable = object : Runnable {
        override fun run() {
            fetchServerFirmwareVersions()
            versionPollHandler.postDelayed(this, 60_000L)
        }
    }

    private val serviceConnection = object : ServiceConnection {
        override fun onServiceConnected(name: ComponentName?, service: IBinder?) {
            val binder = service as BleService.LocalBinder
            bleService = binder.getService()
            serviceBound = true
            statusText.text = bleService?.currentStatus ?: "Connected to service"
            refreshDeviceList()
        }

        override fun onServiceDisconnected(name: ComponentName?) {
            bleService = null
            serviceBound = false
        }
    }

    private val dataReceiver = object : BroadcastReceiver() {
        override fun onReceive(context: Context?, intent: Intent?) {
            when (intent?.action) {
                StatusNotifier.ACTION_DATA_UPDATED -> {
                    refreshDeviceList()
                }
                StatusNotifier.ACTION_STATUS_UPDATED -> {
                    val status = intent.getStringExtra(StatusNotifier.EXTRA_STATUS)
                    statusText.text = status
                }
                StatusNotifier.ACTION_DEVICES_CHANGED -> {
                    refreshDeviceList()
                    fetchServerFirmwareVersions()
                }
            }
        }
    }

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        setContentView(R.layout.activity_main)

        statusText = findViewById(R.id.statusText)
        deviceList = findViewById(R.id.deviceList)

        deviceAdapter = DeviceAdapter(
            onRename = { device -> showRenameDialog(device) },
            onRemove = { device -> showRemoveDialog(device) },
            onUpdate = { device -> launchOtaUpdate(device) },
            serverFirmwareVersions = { serverFirmwareVersions }
        )
        deviceList.layoutManager = LinearLayoutManager(this)
        deviceList.adapter = deviceAdapter

        findViewById<Button>(R.id.settingsButton).setOnClickListener {
            showSettingsDialog()
        }

        val bluetoothToggle = findViewById<SwitchCompat>(R.id.bluetoothToggle)
        val prefs = getSharedPreferences("vape_config", MODE_PRIVATE)
        bluetoothToggle.isChecked = prefs.getBoolean("bluetooth_enabled", true)
        bluetoothToggle.setOnCheckedChangeListener { _, isChecked ->
            bleService?.setBluetoothEnabled(isChecked)
        }

        if (!checkPermissions()) {
            requestPermissions()
        } else {
            startBleService()
        }

        fetchServerFirmwareVersions()
        versionPollHandler.postDelayed(versionPollRunnable, 60_000L)
    }

    private fun refreshDeviceList() {
        val devices = bleService?.devices?.values?.toList() ?: emptyList()
        deviceAdapter.submitList(devices)
    }

    private fun launchOtaUpdate(device: VapeDevice) {
        val intent = Intent(this, OtaUpdateActivity::class.java)
        intent.putExtra("device_address", device.address)
        startActivity(intent)
    }

    private fun fetchServerFirmwareVersions() {
        executor.execute {
            try {
                val prefs = getSharedPreferences("vape_config", MODE_PRIVATE)
                val serverUrl = prefs.getString("server_url", "") ?: ""
                if (serverUrl.isBlank()) return@execute

                val baseUrl = try {
                    val parsed = URL(serverUrl)
                    "${parsed.protocol}://${parsed.host}${if (parsed.port != -1 && parsed.port != parsed.defaultPort) ":${parsed.port}" else ""}"
                } catch (_: Exception) { return@execute }

                // Fetch firmware version for each known variant
                val variants = bleService?.devices?.values
                    ?.mapNotNull { it.boardVariant }
                    ?.distinct()
                    ?.ifEmpty { listOf("esp32") }
                    ?: listOf("esp32")

                for (variant in variants) {
                    try {
                        val url = URL("$baseUrl/firmware/latest?variant=$variant")
                        val connection = url.openConnection() as HttpURLConnection
                        connection.requestMethod = "GET"
                        connection.connectTimeout = 10000
                        connection.readTimeout = 10000

                        if (connection.responseCode == 200) {
                            val body = connection.inputStream.bufferedReader().readText()
                            val json = JSONObject(body)
                            val version = json.getString("version")
                            synchronized(serverFirmwareVersions) {
                                serverFirmwareVersions[variant] = version
                            }
                        }
                        connection.disconnect()
                    } catch (e: Exception) {
                        Log.e(TAG, "Failed to fetch server firmware version for variant $variant", e)
                    }
                }
                runOnUiThread { refreshDeviceList() }
            } catch (e: Exception) {
                Log.e(TAG, "Failed to fetch server firmware versions", e)
            }
        }
    }

    private fun showRenameDialog(device: VapeDevice) {
        val input = EditText(this).apply {
            setText(device.name)
            hint = "Vape name"
            setPadding(48, 32, 48, 16)
        }

        AlertDialog.Builder(this)
            .setTitle("Rename Vape")
            .setView(input)
            .setPositiveButton("Save") { _, _ ->
                val newName = input.text.toString().trim()
                if (newName.isNotEmpty()) {
                    bleService?.renameDevice(device.address, newName)
                }
            }
            .setNeutralButton("Reset") { _, _ ->
                bleService?.resetDeviceName(device.address)
            }
            .setNegativeButton("Cancel", null)
            .show()
    }

    private fun showRemoveDialog(device: VapeDevice) {
        AlertDialog.Builder(this)
            .setTitle("Remove Vape")
            .setMessage("Remove '${device.name}' from your devices?")
            .setPositiveButton("Remove") { _, _ ->
                bleService?.removeDevice(device.address)
            }
            .setNegativeButton("Cancel", null)
            .show()
    }

    private fun checkPermissions(): Boolean {
        val permissions = getRequiredPermissions()
        return permissions.all {
            ContextCompat.checkSelfPermission(this, it) == PackageManager.PERMISSION_GRANTED
        }
    }

    private fun getRequiredPermissions(): List<String> {
        val permissions = mutableListOf<String>()
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.S) {
            permissions.add(Manifest.permission.BLUETOOTH_SCAN)
            permissions.add(Manifest.permission.BLUETOOTH_CONNECT)
        } else {
            permissions.add(Manifest.permission.ACCESS_FINE_LOCATION)
        }
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.TIRAMISU) {
            permissions.add(Manifest.permission.POST_NOTIFICATIONS)
        }
        return permissions
    }

    private fun requestPermissions() {
        ActivityCompat.requestPermissions(
            this, getRequiredPermissions().toTypedArray(), REQUEST_PERMISSIONS
        )
    }

    override fun onRequestPermissionsResult(
        requestCode: Int, permissions: Array<out String>, grantResults: IntArray
    ) {
        super.onRequestPermissionsResult(requestCode, permissions, grantResults)
        if (requestCode == REQUEST_PERMISSIONS) {
            if (grantResults.all { it == PackageManager.PERMISSION_GRANTED }) {
                startBleService()
            } else {
                statusText.text = "Permissions required for BLE"
            }
        }
    }

    private fun startBleService() {
        val intent = Intent(this, BleService::class.java)
        startForegroundService(intent)
        bindService(intent, serviceConnection, BIND_AUTO_CREATE)
    }

    private fun showSettingsDialog() {
        val prefs = getSharedPreferences("vape_config", MODE_PRIVATE)

        val layout = LinearLayout(this).apply {
            orientation = LinearLayout.VERTICAL
            setPadding(48, 32, 48, 0)
        }

        val urlInput = EditText(this).apply {
            hint = "Server URL (e.g. https://example.com)"
            setText(prefs.getString("server_url", ""))
        }
        layout.addView(urlInput)

        val tokenInput = EditText(this).apply {
            hint = "Auth Token"
            setText(prefs.getString("auth_token", ""))
        }
        layout.addView(tokenInput)

        AlertDialog.Builder(this)
            .setTitle("Server Settings")
            .setView(layout)
            .setPositiveButton("Save") { _, _ ->
                prefs.edit()
                    .putString("server_url", urlInput.text.toString().trim())
                    .putString("auth_token", tokenInput.text.toString().trim())
                    .apply()
            }
            .setNegativeButton("Cancel", null)
            .show()
    }

    override fun onStart() {
        super.onStart()
        val filter = IntentFilter().apply {
            addAction(StatusNotifier.ACTION_DATA_UPDATED)
            addAction(StatusNotifier.ACTION_STATUS_UPDATED)
            addAction(StatusNotifier.ACTION_DEVICES_CHANGED)
        }
        registerReceiver(dataReceiver, filter, RECEIVER_NOT_EXPORTED)
    }

    override fun onStop() {
        super.onStop()
        unregisterReceiver(dataReceiver)
    }

    override fun onDestroy() {
        super.onDestroy()
        versionPollHandler.removeCallbacks(versionPollRunnable)
        if (serviceBound) {
            unbindService(serviceConnection)
            serviceBound = false
        }
    }

    // --- RecyclerView Adapter for device list ---

    inner class DeviceAdapter(
        private val onRename: (VapeDevice) -> Unit,
        private val onRemove: (VapeDevice) -> Unit,
        private val onUpdate: (VapeDevice) -> Unit,
        private val serverFirmwareVersions: () -> Map<String, String>
    ) : RecyclerView.Adapter<DeviceAdapter.ViewHolder>() {

        private var items: List<VapeDevice> = emptyList()

        fun submitList(newItems: List<VapeDevice>) {
            items = newItems.toList()
            notifyDataSetChanged()
        }

        inner class ViewHolder(view: View) : RecyclerView.ViewHolder(view) {
            val nameText: TextView = view.findViewById(R.id.deviceName)
            val vapingIndicator: TextView = view.findViewById(R.id.vapingIndicator)
            val statusText: TextView = view.findViewById(R.id.deviceStatus)
            val versionText: TextView = view.findViewById(R.id.deviceVersion)
            val renameButton: Button = view.findViewById(R.id.renameButton)
            val updateButton: Button = view.findViewById(R.id.updateButton)
            val removeButton: Button = view.findViewById(R.id.removeButton)
        }

        override fun onCreateViewHolder(parent: ViewGroup, viewType: Int): ViewHolder {
            val view = LayoutInflater.from(parent.context)
                .inflate(R.layout.item_device, parent, false)
            return ViewHolder(view)
        }

        override fun onBindViewHolder(holder: ViewHolder, position: Int) {
            val device = items[position]
            holder.nameText.text = device.name
            if (device.coilAActive || device.coilBActive) {
                holder.vapingIndicator.text = "🔴 VAPING"
                holder.vapingIndicator.setTextColor(android.graphics.Color.RED)
                holder.vapingIndicator.visibility = View.VISIBLE
            } else {
                holder.vapingIndicator.visibility = View.GONE
            }
            holder.statusText.text = when {
                device.connected -> "🟢 Connected"
                else -> "⚪ Disconnected"
            }
            holder.renameButton.isEnabled = device.connected
            holder.renameButton.setOnClickListener { onRename(device) }
            holder.removeButton.setOnClickListener { onRemove(device) }

            // Show firmware version info
            val deviceVer = device.firmwareVersion
            val variant = device.boardVariant ?: "esp32"
            val serverVer = serverFirmwareVersions()[variant]
            if (deviceVer != null) {
                val versionInfo = buildString {
                    append("FW: v$deviceVer")
                    if (serverVer != null) append(" · Server: v$serverVer")
                }
                holder.versionText.text = versionInfo
                holder.versionText.visibility = View.VISIBLE
            } else {
                holder.versionText.visibility = View.GONE
            }

            // Show update button only if device is connected, has a firmware version,
            // and that version differs from the server's latest
            val updateAvailable = device.connected && deviceVer != null && serverVer != null && deviceVer != serverVer
            holder.updateButton.visibility = if (updateAvailable) View.VISIBLE else View.GONE
            holder.updateButton.setOnClickListener { onUpdate(device) }
        }

        override fun getItemCount() = items.size
    }
}
