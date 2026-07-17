#pragma once

// OTA BLE UUIDs — must match the companion app
#define OTA_SERVICE_UUID  "fb1e4001-54ae-4a28-9f74-dfccb248601d"
#define OTA_VERSION_UUID  "fb1e4004-54ae-4a28-9f74-dfccb248601d"

// Must be called after Bluefruit.begin() and before Advertising.start().
// Exposes a read-only version characteristic so the app can determine
// whether a firmware update is needed.  The actual OTA transfer is
// handled by BLEDfu (Nordic DFU).
void otaInit();
