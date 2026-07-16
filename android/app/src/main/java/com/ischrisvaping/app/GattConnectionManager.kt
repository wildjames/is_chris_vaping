package com.ischrisvaping.app

import android.annotation.SuppressLint
import android.bluetooth.*
import android.bluetooth.le.BluetoothLeScanner
import android.bluetooth.le.ScanCallback
import android.bluetooth.le.ScanFilter
import android.bluetooth.le.ScanResult
import android.bluetooth.le.ScanSettings
import android.os.Handler
import android.os.Looper
import android.os.ParcelUuid
import android.util.Log
import java.util.UUID

class GattConnectionManager(
    private val deviceRepository: DeviceRepository,
    private val stateTracker: VapeStateTracker,
    private val statusNotifier: StatusNotifier
) {

    companion object {
        private const val TAG = "GattConnectionManager"
        private const val SCAN_WINDOW_MS = 30000L
        private const val RECONNECT_DELAY_MS = 2000L
        private const val NAME_READ_DELAY_MS = 500L
        private const val VERSION_READ_DELAY_MS = 1000L

        val SERVICE_UUID: UUID = UUID.fromString("189a9192-f68f-4ac4-962e-d70e7c3755a0")
        val CHARACTERISTIC_UUID: UUID = UUID.fromString("5cf4a205-84e1-42ad-ac23-e5adc776a992")
        val NAME_CHARACTERISTIC_UUID: UUID = UUID.fromString("5cf4a205-84e1-42ad-ac23-e5adc776a993")
        val CCCD_UUID: UUID = UUID.fromString("00002902-0000-1000-8000-00805f9b34fb")

        val OTA_SERVICE_UUID: UUID = UUID.fromString("fb1e4001-54ae-4a28-9f74-dfccb248601d")
        val OTA_VERSION_UUID: UUID = UUID.fromString("fb1e4004-54ae-4a28-9f74-dfccb248601d")
        val OTA_VARIANT_UUID: UUID = UUID.fromString("fb1e4005-54ae-4a28-9f74-dfccb248601d")
    }

    interface GattEventListener {
        fun onCharacteristicChanged(characteristic: BluetoothGattCharacteristic, value: ByteArray)
        fun onCharacteristicRead(characteristic: BluetoothGattCharacteristic, value: ByteArray, status: Int)
        fun onCharacteristicWrite(characteristic: BluetoothGattCharacteristic, status: Int)
        fun onDescriptorWrite(descriptor: BluetoothGattDescriptor, status: Int)
        fun onMtuChanged(mtu: Int)
        fun onReadRemoteRssi(rssi: Int) {}
        fun onConnectionStateChange(device: VapeDevice, connected: Boolean) {}
    }

    var gattEventListener: GattEventListener? = null
    var selectedDeviceAddress: String? = null

    val gatt: BluetoothGatt?
        get() = selectedDeviceAddress?.let { deviceRepository.get(it)?.gatt }
            ?: deviceRepository.devices.values.firstOrNull { it.connected }?.gatt

    private var bluetoothLeScanner: BluetoothLeScanner? = null
    private var isScanning = false
    private var isEnabled = true

    private val mainHandler = Handler(Looper.getMainLooper())

    fun initialize(scanner: BluetoothLeScanner?) {
        bluetoothLeScanner = scanner
    }

    // --- Scanning ---

    @SuppressLint("MissingPermission")
    fun startScan() {
        if (!isEnabled || isScanning) return

        val filter = ScanFilter.Builder()
            .setServiceUuid(ParcelUuid(SERVICE_UUID))
            .build()

        val settings = ScanSettings.Builder()
            .setScanMode(ScanSettings.SCAN_MODE_LOW_POWER)
            .build()

        statusNotifier.updateStatus("Scanning for vapes...")
        bluetoothLeScanner?.startScan(listOf(filter), settings, scanCallback)
        isScanning = true

        mainHandler.postDelayed(scanRestartRunnable, SCAN_WINDOW_MS)
    }

    @SuppressLint("MissingPermission")
    fun stopScan() {
        if (!isScanning) return
        bluetoothLeScanner?.stopScan(scanCallback)
        isScanning = false
        mainHandler.removeCallbacks(scanRestartRunnable)
    }

    @SuppressLint("MissingPermission")
    fun setEnabled(enabled: Boolean) {
        isEnabled = enabled
        if (enabled) {
            startScan()
        } else {
            stopScan()
            for (device in deviceRepository.devices.values) {
                if (device.connected) {
                    stateTracker.handleDisconnection(device)
                }
                device.gatt?.disconnect()
                device.gatt?.close()
                device.gatt = null
                device.connected = false
            }
            statusNotifier.updateStatus("Bluetooth disabled")
            statusNotifier.updateNotification("Bluetooth disabled", ongoing = false)
            statusNotifier.broadcastDevicesChanged()
        }
    }

    @SuppressLint("MissingPermission")
    fun disconnectAll() {
        stopScan()
        for (device in deviceRepository.devices.values) {
            device.gatt?.disconnect()
            device.gatt?.close()
        }
    }

    @SuppressLint("MissingPermission")
    fun disconnectDevice(address: String) {
        deviceRepository.get(address)?.let { device ->
            device.gatt?.disconnect()
            device.gatt?.close()
            device.gatt = null
            device.connected = false
        }
    }

    @SuppressLint("MissingPermission")
    fun writeNameToDevice(device: VapeDevice, name: String) {
        val gatt = device.gatt ?: return
        val service = gatt.getService(SERVICE_UUID) ?: return
        val nameChar = service.getCharacteristic(NAME_CHARACTERISTIC_UUID) ?: return
        gatt.writeCharacteristic(nameChar, name.toByteArray(Charsets.UTF_8), BluetoothGattCharacteristic.WRITE_TYPE_DEFAULT)
        Log.d(TAG, "Writing name '$name' to device ${device.address}")
    }

    @SuppressLint("MissingPermission")
    fun readNameFromDevice(device: VapeDevice) {
        val gatt = device.gatt ?: return
        val service = gatt.getService(SERVICE_UUID) ?: return
        val nameChar = service.getCharacteristic(NAME_CHARACTERISTIC_UUID) ?: return
        gatt.readCharacteristic(nameChar)
        Log.d(TAG, "Reading name from device ${device.address}")
    }

    // --- Private ---

    private val scanRestartRunnable = Runnable {
        @SuppressLint("MissingPermission")
        if (isScanning) {
            bluetoothLeScanner?.stopScan(scanCallback)
            isScanning = false
        }
        if (deviceRepository.hasDisconnectedDevices() && isEnabled) {
            startScan()
        } else {
            statusNotifier.updateStatus(statusNotifier.getOverallStatus(deviceRepository.devices.values))
        }
    }

    private val scanCallback = object : ScanCallback() {
        @SuppressLint("MissingPermission")
        override fun onScanResult(callbackType: Int, result: ScanResult) {
            val address = result.device.address
            val deviceName = result.device.name ?: "Unknown Vape"

            Log.d(TAG, "Found device: $deviceName - $address")

            val knownDevice = deviceRepository.get(address)
            if (knownDevice != null && !knownDevice.connected) {
                connectToDevice(result.device, knownDevice)
            } else if (knownDevice == null) {
                val newDevice = deviceRepository.add(address, deviceName)
                connectToDevice(result.device, newDevice)
                statusNotifier.broadcastDevicesChanged()
            }
        }

        override fun onScanFailed(errorCode: Int) {
            Log.e(TAG, "Scan failed: $errorCode")
            statusNotifier.updateStatus("Scan failed (error $errorCode)")
            isScanning = false
        }
    }

    @SuppressLint("MissingPermission")
    private fun connectToDevice(device: BluetoothDevice, vapeDevice: VapeDevice) {
        statusNotifier.updateStatus("Connecting to ${vapeDevice.name}...")
        vapeDevice.gatt = device.connectGatt(null, true, createGattCallback(vapeDevice), BluetoothDevice.TRANSPORT_LE)
    }

    private fun createGattCallback(vapeDevice: VapeDevice) = object : BluetoothGattCallback() {
        @SuppressLint("MissingPermission")
        override fun onConnectionStateChange(gatt: BluetoothGatt, status: Int, newState: Int) {
            when (newState) {
                BluetoothProfile.STATE_CONNECTED -> {
                    Log.d(TAG, "Connected to ${vapeDevice.name} (${vapeDevice.address})")
                    vapeDevice.connected = true
                    vapeDevice.gatt = gatt
                    statusNotifier.updateStatus("Connected to ${vapeDevice.name}. Discovering services...")
                    gatt.discoverServices()
                    statusNotifier.broadcastDevicesChanged()
                    if (vapeDevice.address == selectedDeviceAddress) {
                        gattEventListener?.onConnectionStateChange(vapeDevice, true)
                    }
                }
                BluetoothProfile.STATE_DISCONNECTED -> {
                    Log.d(TAG, "Disconnected from ${vapeDevice.name} (${vapeDevice.address})")
                    if (vapeDevice.address == selectedDeviceAddress) {
                        gattEventListener?.onConnectionStateChange(vapeDevice, false)
                    }
                    stateTracker.handleDisconnection(vapeDevice)
                    vapeDevice.connected = false
                    vapeDevice.gatt?.close()
                    vapeDevice.gatt = null
                    statusNotifier.broadcastDevicesChanged()

                    if (isEnabled) {
                        statusNotifier.updateStatus(statusNotifier.getOverallStatus(deviceRepository.devices.values))
                        mainHandler.postDelayed({ startScan() }, RECONNECT_DELAY_MS)
                    }
                }
            }
        }

        override fun onMtuChanged(gatt: BluetoothGatt, mtu: Int, status: Int) {
            if (vapeDevice.address == selectedDeviceAddress) {
                gattEventListener?.onMtuChanged(mtu)
            }
        }

        @SuppressLint("MissingPermission")
        override fun onServicesDiscovered(gatt: BluetoothGatt, status: Int) {
            if (status != BluetoothGatt.GATT_SUCCESS) {
                statusNotifier.updateStatus("Service discovery failed for ${vapeDevice.name}")
                return
            }

            val service = gatt.getService(SERVICE_UUID)
            if (service == null) {
                statusNotifier.updateStatus("Service not found on ${vapeDevice.name}")
                return
            }

            val characteristic = service.getCharacteristic(CHARACTERISTIC_UUID)
            if (characteristic == null) {
                statusNotifier.updateStatus("Characteristic not found on ${vapeDevice.name}")
                return
            }

            gatt.setCharacteristicNotification(characteristic, true)
            val descriptor = characteristic.getDescriptor(CCCD_UUID)
            if (descriptor != null) {
                gatt.writeDescriptor(descriptor, BluetoothGattDescriptor.ENABLE_NOTIFICATION_VALUE)
            }

            // Read the device name from the ESP32
            val nameChar = service.getCharacteristic(NAME_CHARACTERISTIC_UUID)
            if (nameChar != null) {
                mainHandler.postDelayed({ gatt.readCharacteristic(nameChar) }, NAME_READ_DELAY_MS)
            }

            // Read firmware version from OTA service
            val otaService = gatt.getService(OTA_SERVICE_UUID)
            val versionChar = otaService?.getCharacteristic(OTA_VERSION_UUID)
            if (versionChar != null) {
                mainHandler.postDelayed({ gatt.readCharacteristic(versionChar) }, VERSION_READ_DELAY_MS)
            }

            // Read board variant from OTA service
            val variantChar = otaService?.getCharacteristic(OTA_VARIANT_UUID)
            if (variantChar != null) {
                mainHandler.postDelayed({ gatt.readCharacteristic(variantChar) }, VERSION_READ_DELAY_MS + 500L)
            }

            statusNotifier.updateStatus(statusNotifier.getOverallStatus(deviceRepository.devices.values))
        }

        override fun onCharacteristicRead(
            gatt: BluetoothGatt, characteristic: BluetoothGattCharacteristic, value: ByteArray, status: Int
        ) {
            if (vapeDevice.address == selectedDeviceAddress) {
                gattEventListener?.onCharacteristicRead(characteristic, value, status)
            }
            if (status == BluetoothGatt.GATT_SUCCESS) {
                if (characteristic.uuid == NAME_CHARACTERISTIC_UUID) {
                    val name = value.toString(Charsets.UTF_8).trim()
                    if (name.isNotEmpty() && name != vapeDevice.name) {
                        Log.d(TAG, "Read device name from ESP32: $name (was: ${vapeDevice.name})")
                        vapeDevice.name = name
                        deviceRepository.save()
                        statusNotifier.broadcastDevicesChanged()
                    }
                } else if (characteristic.uuid == OTA_VERSION_UUID) {
                    val version = value.toString(Charsets.UTF_8).trim()
                    if (version.isNotEmpty()) {
                        Log.d(TAG, "Read firmware version from ${vapeDevice.name}: $version")
                        vapeDevice.firmwareVersion = version
                        statusNotifier.broadcastDevicesChanged()
                    }
                } else if (characteristic.uuid == OTA_VARIANT_UUID) {
                    val variant = value.toString(Charsets.UTF_8).trim()
                    if (variant.isNotEmpty()) {
                        Log.d(TAG, "Read board variant from ${vapeDevice.name}: $variant")
                        vapeDevice.boardVariant = variant
                        statusNotifier.broadcastDevicesChanged()
                    }
                } else if (characteristic.uuid == CHARACTERISTIC_UUID) {
                    val text = value.toString(Charsets.UTF_8)
                    Log.d(TAG, "Read value from ${vapeDevice.name}: $text")
                    handleIncomingData(text, vapeDevice)
                }
            }
        }

        override fun onCharacteristicChanged(
            gatt: BluetoothGatt, characteristic: BluetoothGattCharacteristic, value: ByteArray
        ) {
            if (vapeDevice.address == selectedDeviceAddress) {
                gattEventListener?.onCharacteristicChanged(characteristic, value)
            }
            if (characteristic.uuid == CHARACTERISTIC_UUID) {
                val text = value.toString(Charsets.UTF_8)
                Log.d(TAG, "Notification from ${vapeDevice.name}: $text")
                handleIncomingData(text, vapeDevice)
            }
        }

        override fun onCharacteristicWrite(gatt: BluetoothGatt, characteristic: BluetoothGattCharacteristic, status: Int) {
            if (vapeDevice.address == selectedDeviceAddress) {
                gattEventListener?.onCharacteristicWrite(characteristic, status)
            }
        }

        override fun onDescriptorWrite(gatt: BluetoothGatt, descriptor: BluetoothGattDescriptor, status: Int) {
            if (vapeDevice.address == selectedDeviceAddress) {
                gattEventListener?.onDescriptorWrite(descriptor, status)
            }
        }

        override fun onReadRemoteRssi(gatt: BluetoothGatt, rssi: Int, status: Int) {
            if (status == BluetoothGatt.GATT_SUCCESS && vapeDevice.address == selectedDeviceAddress) {
                gattEventListener?.onReadRemoteRssi(rssi)
            }
        }
    }

    private fun handleIncomingData(text: String, device: VapeDevice) {
        if (!isEnabled) return
        stateTracker.handleMessage(text, device)
        statusNotifier.updateData(text, device.address)
        statusNotifier.updateNotification(statusNotifier.getOverallStatus(deviceRepository.devices.values))
        statusNotifier.broadcastDevicesChanged()
    }
}
