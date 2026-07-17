package com.ischrisvaping.app

import android.app.*
import android.bluetooth.*
import android.content.Intent
import android.content.pm.ServiceInfo
import android.os.Binder
import android.os.IBinder
import java.util.concurrent.ConcurrentHashMap

class BleService : Service() {

    companion object {
        private const val TAG = "BleService"
    }

    // Expose these for backward compatibility with MainActivity and OtaUpdateActivity
    val devices: ConcurrentHashMap<String, VapeDevice> get() = deviceRepository.devices
    var currentData: String = ""
        get() = statusNotifier.currentData
        private set
    var currentStatus: String = "Idle"
        get() = statusNotifier.currentStatus
        private set

    var isBluetoothEnabled = true
        private set

    // OTA support
    var selectedDeviceAddress: String?
        get() = connectionManager.selectedDeviceAddress
        set(value) { connectionManager.selectedDeviceAddress = value }
    val gatt: BluetoothGatt? get() = connectionManager.gatt
    var gattEventListener: GattConnectionManager.GattEventListener?
        get() = connectionManager.gattEventListener
        set(value) { connectionManager.gattEventListener = value }

    private lateinit var deviceRepository: DeviceRepository
    private lateinit var serverClient: ServerClient
    private lateinit var stateTracker: VapeStateTracker
    private lateinit var statusNotifier: StatusNotifier
    private lateinit var connectionManager: GattConnectionManager

    private val binder = LocalBinder()

    inner class LocalBinder : Binder() {
        fun getService(): BleService = this@BleService
    }

    override fun onBind(intent: Intent?): IBinder = binder

    override fun onCreate() {
        super.onCreate()

        // Initialize components
        deviceRepository = DeviceRepository(this)
        serverClient = ServerClient(this)
        stateTracker = VapeStateTracker(serverClient)
        statusNotifier = StatusNotifier(this)
        connectionManager = GattConnectionManager(deviceRepository, stateTracker, statusNotifier)

        statusNotifier.createNotificationChannel()
        deviceRepository.load()

        val bluetoothManager = getSystemService(BLUETOOTH_SERVICE) as BluetoothManager
        connectionManager.initialize(bluetoothManager.adapter?.bluetoothLeScanner)
    }

    override fun onStartCommand(intent: Intent?, flags: Int, startId: Int): Int {
        if (intent?.action == StatusNotifier.ACTION_NOTIFICATION_DISMISSED) {
            if (isBluetoothEnabled) {
                val notificationManager = getSystemService(NotificationManager::class.java)
                notificationManager.notify(
                    StatusNotifier.NOTIFICATION_ID,
                    statusNotifier.buildNotification(statusNotifier.currentStatus)
                )
            }
            return START_STICKY
        }

        startForeground(
            StatusNotifier.NOTIFICATION_ID,
            statusNotifier.buildNotification("Searching for devices..."),
            ServiceInfo.FOREGROUND_SERVICE_TYPE_CONNECTED_DEVICE
        )

        val prefs = getSharedPreferences("vape_config", MODE_PRIVATE)
        isBluetoothEnabled = prefs.getBoolean("bluetooth_enabled", true)
        if (isBluetoothEnabled) {
            connectionManager.startScan()
        } else {
            statusNotifier.updateStatus("Bluetooth disabled")
        }
        return START_STICKY
    }

    // --- Public API for MainActivity ---

    fun setBluetoothEnabled(enabled: Boolean) {
        isBluetoothEnabled = enabled
        val prefs = getSharedPreferences("vape_config", MODE_PRIVATE)
        prefs.edit().putBoolean("bluetooth_enabled", enabled).apply()
        connectionManager.setEnabled(enabled)
    }

    fun addDevice(address: String, name: String) {
        deviceRepository.add(address, name)
        statusNotifier.broadcastDevicesChanged()
    }

    fun removeDevice(address: String) {
        connectionManager.disconnectDevice(address)
        deviceRepository.remove(address)
        statusNotifier.broadcastDevicesChanged()
    }

    fun renameDevice(address: String, newName: String) {
        val device = deviceRepository.get(address) ?: return
        val oldName = device.name
        val sendOldName = !oldName.matches(Regex("""My Vape \d{4}"""))
        serverClient.postRenameDevice(if (sendOldName) oldName else null, newName) {
            deviceRepository.rename(address, newName)
            connectionManager.writeNameToDevice(device, newName)
            statusNotifier.broadcastDevicesChanged()
        }
    }

    fun resetDeviceName(address: String) {
        val device = deviceRepository.get(address) ?: return
        val newName = "My Vape %04d".format((0..9999).random())
        deviceRepository.rename(address, newName)
        connectionManager.writeNameToDevice(device, newName)
        statusNotifier.broadcastDevicesChanged()
    }

    /** Disconnect a single device's GATT connection without removing it. */
    fun disconnectDevice(address: String) {
        connectionManager.disconnectDevice(address)
    }

    override fun onDestroy() {
        super.onDestroy()
        connectionManager.disconnectAll()
        serverClient.shutdown()
    }
}
