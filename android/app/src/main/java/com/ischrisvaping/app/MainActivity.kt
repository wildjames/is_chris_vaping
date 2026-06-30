package com.ischrisvaping.app

import android.Manifest
import android.annotation.SuppressLint
import android.content.*
import android.content.pm.PackageManager
import android.os.Build
import android.os.Bundle
import android.os.IBinder
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

class MainActivity : AppCompatActivity() {

    companion object {
        private const val REQUEST_PERMISSIONS = 1
    }

    private lateinit var statusText: TextView
    private lateinit var dataText: TextView
    private lateinit var deviceList: RecyclerView
    private lateinit var deviceAdapter: DeviceAdapter

    private var bleService: BleService? = null
    private var serviceBound = false

    private val serviceConnection = object : ServiceConnection {
        override fun onServiceConnected(name: ComponentName?, service: IBinder?) {
            val binder = service as BleService.LocalBinder
            bleService = binder.getService()
            serviceBound = true
            statusText.text = bleService?.currentStatus ?: "Connected to service"
            val data = bleService?.currentData
            if (!data.isNullOrEmpty()) {
                dataText.text = data
            }
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
                    val data = intent.getStringExtra(StatusNotifier.EXTRA_DATA)
                    dataText.text = data
                }
                StatusNotifier.ACTION_STATUS_UPDATED -> {
                    val status = intent.getStringExtra(StatusNotifier.EXTRA_STATUS)
                    statusText.text = status
                }
                StatusNotifier.ACTION_DEVICES_CHANGED -> {
                    refreshDeviceList()
                }
            }
        }
    }

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        setContentView(R.layout.activity_main)

        statusText = findViewById(R.id.statusText)
        dataText = findViewById(R.id.dataText)
        deviceList = findViewById(R.id.deviceList)

        deviceAdapter = DeviceAdapter(
            onRename = { device -> showRenameDialog(device) },
            onRemove = { device -> showRemoveDialog(device) }
        )
        deviceList.layoutManager = LinearLayoutManager(this)
        deviceList.adapter = deviceAdapter

        findViewById<Button>(R.id.settingsButton).setOnClickListener {
            showSettingsDialog()
        }

        findViewById<Button>(R.id.otaButton).setOnClickListener {
            startActivity(Intent(this, OtaUpdateActivity::class.java))
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
    }

    private fun refreshDeviceList() {
        val devices = bleService?.devices?.values?.toList() ?: emptyList()
        deviceAdapter.submitList(devices)
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
        if (serviceBound) {
            unbindService(serviceConnection)
            serviceBound = false
        }
    }

    // --- RecyclerView Adapter for device list ---

    inner class DeviceAdapter(
        private val onRename: (VapeDevice) -> Unit,
        private val onRemove: (VapeDevice) -> Unit
    ) : RecyclerView.Adapter<DeviceAdapter.ViewHolder>() {

        private var items: List<VapeDevice> = emptyList()

        fun submitList(newItems: List<VapeDevice>) {
            items = newItems.toList()
            notifyDataSetChanged()
        }

        inner class ViewHolder(view: View) : RecyclerView.ViewHolder(view) {
            val nameText: TextView = view.findViewById(R.id.deviceName)
            val statusText: TextView = view.findViewById(R.id.deviceStatus)
            val renameButton: Button = view.findViewById(R.id.renameButton)
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
            holder.statusText.text = when {
                device.coilAActive || device.coilBActive -> "🔴 Vaping"
                device.connected -> "🟢 Connected"
                else -> "⚪ Disconnected"
            }
            holder.renameButton.setOnClickListener { onRename(device) }
            holder.removeButton.setOnClickListener { onRemove(device) }
        }

        override fun getItemCount() = items.size
    }
}
