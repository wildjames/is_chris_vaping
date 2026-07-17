# OTA Update Code Review

Review of the OTA firmware update implementation across firmware (nRF52840), server (Flask), and Android companion app (Kotlin).

---

## OTA Update Flow (as implemented)

```
1.  Android app connects to nRF52840 via BLE
2.  GattConnectionManager discovers OTA service, reads OTA_VERSION_UUID
    → device firmware version stored in VapeDevice.firmwareVersion
3.  User opens OtaUpdateActivity (launched from MainActivity)
4.  Activity binds to BleService, gets existing GATT connection
5.  Requests high-priority connection interval + MTU 512
6.  After MTU negotiation, discovers OTA service and reads version characteristic again
7.  Concurrently fetches GET /firmware/latest from server → {version, sha256}
8.  Compares device version vs server version (simple string inequality)
9.  If different, enables "Start Update" button
10. User taps button → downloads GET /firmware/download → byte array
11. Validates SHA-256 of download against server metadata
12. Writes bytes to cache file as firmware_dfu.zip
13. Disconnects app's GATT connection via BleService
14. Starts Nordic DFU library via DfuServiceInitiator:
    - setForceScanningForNewAddressInLegacyDfu(true)
    - setPacketsReceiptNotificationsValue(8)
    - setNumberOfRetries(3)
15. DFU library connects, triggers bootloader entry (GPREGRET=0xA8), scans for
    bootloader on address+1, transfers firmware via Legacy DFU protocol
16. On completion, app polls for device reconnection (30s timeout)
17. Re-reads OTA_VERSION_UUID to confirm new version
```

This flow is fundamentally sound. The research document (`OTA_RESEARCH.md`) was clearly used to inform the implementation, and the critical issues it identified (ZIP format, address+1 scanning, PRN limit, GATT disconnect) are all addressed.

---

## Layer-by-Layer Analysis

### 1. Firmware (`firmware/nrf52840/`)

#### What's good

- **Minimal and correct.** The firmware's OTA responsibility is tiny: expose a version string and initialise the `BLEDfu` service. Both are done correctly.
- **BLEDfu initialised before advertising** in `bluetooth.cpp` (required for the bootloader entry mechanism to work).
- **Bonding enabled with Just Works** — shares the IRK, which helps the bootloader resolve the phone's random resolvable address after reboot.
- **Version characteristic is read-only** with `SECMODE_NO_ACCESS` for writes — correct.

#### Issues

| # | Severity | Issue | Details |
|---|----------|-------|---------|
| F1 | **Low** | `FIRMWARE_VERSION` is always `"<dev>"` | `version.h` defines `FIRMWARE_VERSION` as `"<dev>"`. The Makefile doesn't substitute it. Without CI doing a `sed` or a `-DFIRMWARE_VERSION='"x.y.z"'` build flag, the device always reports `<dev>`. The Android app will then compare `"<dev>"` against the server's version, which means **every server upload will trigger an "update available" prompt**, even if the firmware is the same. This is incorrect behaviour — the version comparison is meaningless unless CI substitutes it. |
| F2 | **Low** | `otaVersionChar.setMaxLen(16)` | The version string is capped at 16 bytes. Fine for semver (`1.2.3` = 5 chars), but worth noting if you ever use longer version strings. Not a real issue for now. |
| F3 | **Info** | `--sd-req 0xFFFE` wildcard | The Makefile's `dfu-package` target uses `--sd-req 0xFFFE` (accept any SoftDevice). This is convenient but means the package won't reject a flash onto a board running an incompatible SoftDevice. Given you only support one board (Seeed XIAO nRF52840 with S140 v7.x), this is fine in practice. |

#### Verdict

The firmware OTA code is clean, minimal, and correct. No changes needed beyond fixing the version injection in CI/build pipeline.

---

### 2. Server (`server/`)

#### What's good

- **Proper ZIP validation on upload** — checks `zipfile.is_zipfile()` and that `manifest.json` exists inside the ZIP. This prevents uploading raw binaries or garbage.
- **SHA-256 computed from disk on `/firmware/latest`** — the hash is recomputed from the actual file rather than trusting the DB, so it can't go stale if the file is replaced outside the upload endpoint.
- **Bearer token auth** on upload and vape-update endpoints.
- **Firmware metadata in MariaDB** — version history is preserved.

#### Issues

| # | Severity | Issue | Details |
|---|----------|-------|---------|
| S1 | **Medium** | **No authentication on `/firmware/download`** | Anyone who knows the URL can download the firmware binary. While the firmware itself is unlikely to be sensitive, unauthenticated access means an attacker could repeatedly download large files to exhaust bandwidth/disk I/O. More importantly, the lack of auth means there's no access control consistency — upload requires a token but download doesn't. Consider whether this is intentional (public firmware) or an oversight. |
| S2 | **Medium** | **No `Content-Length` header on download** | `send_file()` should handle this, but the Android client uses `HttpURLConnection` which benefits from knowing the content length up front for progress reporting and pre-allocating buffers. Flask's `send_file` does set it for on-disk files, so this is probably fine, but worth verifying. |
| S3 | **Medium** | **Single firmware file slot** | The server stores only one firmware file at `/firmware/firmware.zip` regardless of version. Uploading a new version overwrites the old one. The `Firmware` table in the DB stores version history, but there's no way to roll back to a previous version since the file is gone. For a single-device hobby project this is acceptable, but it's worth knowing the limitation. |
| S4 | **Medium** | **Race condition on upload** | If two uploads happen simultaneously, they both write to `/firmware/firmware.zip`. One wins the file, but both add rows to the `Firmware` table. The DB could end up with a version that doesn't match the file on disk. The `sha256` recomputation in `/firmware/latest` mitigates the metadata mismatch, but the wrong version string would be served. |
| S5 | **Low** | **`variant` field unused** | The `Firmware` model has a `variant` column (defaults to `"nrf52840"`), but the server never filters on it. Since you only support one board this is dead code. Not harmful, just unnecessary. |
| S6 | **Low** | **`import zipfile` inside function** | In `/firmware/upload`, `zipfile` is imported at function scope rather than module level. This is a minor style issue — it works, but is unconventional. |
| S7 | **Low** | **`db_persist_vape_update` receives `state` dict, not used correctly** | This isn't OTA-specific but: the function receives the full `state` dict as the 4th argument (named `state`) but also receives `timestamp` as the 5th. The function signature works, but passing the full mutable state dict to a background thread is a subtle race if the dict is mutated after submission. In practice, the dict is replaced (not mutated) on each request, so this is safe — but it's a latent risk. |

#### Verdict

The server OTA code is solid for a personal project. The main risk is the single-file-slot design (S3) and the lack of download auth (S1). Neither is critical for your use case.

---

### 3. Android App (`android/`)

#### What's good

- **Nordic DFU library v2.4.2** — correctly pinned below the broken v2.9.0+ (per OTA_RESEARCH.md issue #491).
- **`DfuServiceInitiator` configuration is correct:**
  - `setForceScanningForNewAddressInLegacyDfu(true)` — critical for Adafruit bootloader.
  - `setPacketsReceiptNotificationsValue(8)` — matches Adafruit bootloader's buffer limit.
  - `setNumberOfRetries(3)` — handles flaky BLE.
- **GATT disconnected before DFU start** — the app calls `bleService?.disconnectDevice(address)` and nulls `bluetoothGatt` before starting the DFU library. This is the #1 cause of DFU failures, and it's handled correctly.
- **SHA-256 verification** of downloaded firmware before applying.
- **DfuService** wrapper correctly creates the notification channel in `onCreate()`.
- **Post-update verification** — reconnects and re-reads the version characteristic.

#### Issues

| # | Severity | Issue | Details |
|---|----------|-------|---------|
| A1 | **High** | **`getServerBaseUrl()` protocol validation is wrong** | The method checks `if (parsed.protocol != "https")` and returns `""` (empty string) if the URL isn't HTTPS. But it logs and continues — the calling code doesn't check for empty and will construct URLs like `"/firmware/latest"` (no host), causing a `MalformedURLException`. The check is well-intentioned (enforce HTTPS) but the error path is incomplete. If the server URL is misconfigured as HTTP, the user sees "Server: unreachable" with no indication it's a protocol issue. Either crash loudly, show a clear error message, or handle the empty return properly. |
| A2 | **High** | **No delay between GATT disconnect and DFU start** | `performNordicDfuUpdate()` calls `bleService?.disconnectDevice(address)` immediately followed by `DfuServiceInitiator(...).start()`. On some Android devices, the BLE stack needs a moment to fully release the connection. The OTA_RESEARCH.md even mentions this: *"Small delay may help on some Android versions."* The lack of delay can cause the DFU library's connect attempt to fail because the old connection hasn't fully torn down yet. Consider adding a 500-1000ms delay. |
| A3 | **Medium** | **Firmware temp file not cleaned up** | `performNordicDfuUpdate()` writes the firmware to `File(cacheDir, "firmware_dfu.zip")` but never deletes it after the DFU completes (or fails). The cache dir can be reclaimed by the OS, but explicit cleanup in `onDfuCompleted` and `onError` would be better practice. |
| A4 | **Medium** | **`firmwareData` held in memory indefinitely** | After downloading, the firmware bytes are stored in `firmwareData: ByteArray?`. This is never cleared, even after the DFU is complete. For a typical firmware (~100-300KB) this isn't huge, but it's wasteful. Set `firmwareData = null` after writing to the temp file. |
| A5 | **Medium** | **Reconnect polling uses `Thread.sleep()` on executor thread** | `waitForReconnect()` polls with `Thread.sleep(500)` in a loop for up to 30 seconds. This blocks the single-thread executor the entire time, preventing any other executor tasks from running. Since the executor is also used for `fetchServerFirmwareInfo()` and `downloadFirmware()`, this could theoretically block if those were called during reconnect. In practice, they aren't — but it's a fragile design. A `Handler.postDelayed` loop on the main thread checking connection state would be cleaner. |
| A6 | **Medium** | **Version comparison is string inequality** | `checkUpdateAvailable()` compares `deviceVer != serverVer`. This means: (1) if the device has a *newer* version than the server, it still offers a "downgrade" with no warning; (2) version `"1.10.0"` vs `"1.9.0"` works correctly only because it's inequality, not ordering. This is fine if you never need to skip updates or prevent downgrades, but it's worth documenting. |
| A7 | **Medium** | **MTU request of 512 may fail silently** | `gatt.requestMtu(512)` is called, but the BLE spec maximum for ATT_MTU is 517 (and many devices negotiate lower). If the negotiation fails or returns a lower value, the code continues fine — the MTU value is stored but never actually used anywhere in the OTA flow (the Nordic DFU library handles its own MTU negotiation). The MTU request is thus unnecessary for OTA — it only helps if you need large reads from the version characteristic (which is 16 bytes max). Not harmful, just pointless overhead. |
| A8 | **Low** | **RSSI polling continues during DFU** | `rssiRunnable` polls every 2 seconds, but the GATT connection is disconnected during DFU. The `bluetoothGatt?.readRemoteRssi()` call will either no-op (null GATT) or fail silently. It's stopped in `waitForReconnect()`, but there's a window between DFU start and completion where it runs against a null or disconnected GATT. Harmless but wasteful. |
| A9 | **Low** | **`DfuServiceListenerHelper.registerProgressListener` in `performNordicDfuUpdate`** | The listener is registered just before starting DFU. If the activity is destroyed during DFU (e.g., screen rotation), the listener is unregistered in `onDestroy` but the DFU continues in the foreground service. When the user re-opens the activity, progress isn't resumed. The Nordic DFU library docs recommend registering in `onResume` and unregistering in `onPause` instead. |
| A10 | **Low** | **`executor.shutdown()` in `onDestroy` without `awaitTermination`** | If the executor is running a task (e.g., `waitForReconnect` polling), `shutdown()` won't interrupt it. The task continues running with a reference to the destroyed activity. Use `shutdownNow()` or call `awaitTermination()` if you want a clean shutdown. |

#### Verdict

The Android OTA code is well-structured and handles the critical DFU pitfalls correctly. The highest-priority fix is A2 (delay between disconnect and DFU start), which can cause intermittent DFU failures. A1 (protocol validation) is a UX issue that should also be addressed.

---

## Cross-Cutting Concerns

### Version Management (CI Pipeline Gap)

The most significant gap across the stack is the **version injection pipeline**. Currently:

1. `version.h` always contains `"<dev>"`.
2. The Makefile builds the firmware and generates the DFU ZIP, but doesn't substitute the version.
3. The server's `/firmware/upload` accepts a `version` query parameter, but this is only metadata — it doesn't modify the firmware binary.
4. The Android app compares the device's version (always `"<dev>"`) with the server's version.

**Result:** If the firmware is built without CI version substitution, the device always reports `"<dev>"`, the server always reports whatever version string was passed to the upload endpoint, and these will never match — so the app will **always** offer an update, even if the firmware is identical.

**What's needed:** A CI step (or Makefile enhancement) that:
1. Receives a version string (from git tag, env var, etc.)
2. Substitutes it into `version.h` (via `sed`, PlatformIO build flag, or a template)
3. Builds the firmware
4. Generates the DFU ZIP via `adafruit-nrfutil`
5. Uploads the ZIP to the server with the same version string

### UUID Consistency

The UUIDs are correctly mirrored across all three layers:

| UUID | Firmware (C define) | Android (Kotlin) |
|------|-------------------|-----------------|
| OTA Service | `fb1e4001-54ae-4a28-9f74-dfccb248601d` | `OTA_SERVICE_UUID` |
| OTA Version | `fb1e4004-54ae-4a28-9f74-dfccb248601d` | `OTA_VERSION_UUID` |
| Main Service | `189a9192-f68f-4ac4-962e-d70e7c3755a0` | `SERVICE_UUID` |

These are defined in two places in the Android code (`GattConnectionManager.companion` and `OtaUpdateActivity.companion`). The duplication is a minor maintenance risk — if one is updated without the other, things break silently. Consider a single shared constants file.

### Security

| Area | Status | Notes |
|------|--------|-------|
| Server auth (upload) | ✅ | Bearer token required |
| Server auth (download) | ⚠️ | No auth — intentional? |
| HTTPS enforcement (Android) | ⚠️ | Checked but error handling is broken (A1) |
| Firmware signing | ❌ | Legacy DFU doesn't sign. Any valid DFU ZIP will be accepted by the bootloader. This is inherent to the Adafruit bootloader's design — not something you can fix without switching to Secure DFU (which would require a different bootloader). |
| Checksum verification | ✅ | SHA-256 validated before applying |
| BLE bonding | ✅ | Just Works pairing with IRK sharing |

The biggest security gap is that **the firmware is not cryptographically signed**. An attacker with physical BLE proximity could flash arbitrary firmware to the device. This is a fundamental limitation of Legacy DFU and the Adafruit bootloader. For a personal vape-tracking project, this risk is acceptable. For a commercial product, you'd need to migrate to Secure DFU with signed packages.

---

## Summary of Recommendations

### Must Fix

| # | Issue | Impact |
|---|-------|--------|
| A2 | Add 500-1000ms delay between GATT disconnect and DFU start | Prevents intermittent DFU failures on some Android devices |
| F1 | Implement version injection in build/CI pipeline | Without this, version comparison is meaningless and always triggers updates |

### Should Fix

| # | Issue | Impact |
|---|-------|--------|
| A1 | Fix `getServerBaseUrl()` error handling for non-HTTPS URLs | Users see a confusing "unreachable" error instead of a clear protocol error |
| A3 | Clean up temp firmware file after DFU completes/fails | Prevents stale cache files |
| A4 | Null out `firmwareData` after writing to temp file | Frees ~100-300KB of memory |
| A6 | Document or warn on potential downgrades | Prevents accidental firmware downgrades |
| A9 | Register DFU progress listener in `onResume`/`onPause` instead of ad-hoc | Handles activity recreation during DFU |

### Nice to Have

| # | Issue | Impact |
|---|-------|--------|
| S1 | Decide whether firmware download should require auth | Consistency / minor security hardening |
| S3 | Consider storing versioned firmware files | Enables rollback capability |
| A5 | Replace `Thread.sleep` polling with Handler-based approach | Cleaner architecture, doesn't block executor |
| A8 | Stop RSSI polling when DFU starts | Avoids useless BLE calls during update |
| A10 | Use `shutdownNow()` or `awaitTermination` in `onDestroy` | Clean activity teardown |
| — | Consolidate duplicate UUID constants in Android code | Reduces maintenance risk |
