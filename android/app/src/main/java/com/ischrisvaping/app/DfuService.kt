package com.ischrisvaping.app

import android.app.Activity
import no.nordicsemi.android.dfu.DfuBaseService

/**
 * Thin wrapper required by the Nordic DFU library.
 * All OTA logic is handled by DfuBaseService; this class only declares
 * which Activity to open when the DFU progress notification is tapped.
 */
class DfuService : DfuBaseService() {
    override fun getNotificationTarget(): Class<out Activity> = OtaUpdateActivity::class.java
}
