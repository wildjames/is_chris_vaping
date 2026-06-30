package com.ischrisvaping.app

import android.bluetooth.BluetoothGatt

data class VapeDevice(
    val address: String,
    var name: String,
    var gatt: BluetoothGatt? = null,
    var coilAActive: Boolean = false,
    var coilBActive: Boolean = false,
    var connected: Boolean = false,
    var firmwareVersion: String? = null
)
