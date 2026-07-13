#include "ota.h"
#include "version.h"
#include <bluefruit.h>

// Read-only info service: exposes firmware version and board variant so the
// companion app can determine whether a Nordic DFU update is needed and which
// DFU zip package to download from the server.
// The actual OTA transfer is handled by the BLEDfu service (Nordic DFU
// protocol), which is initialised in bluetooth.cpp.

static BLEService        otaSvc(OTA_SERVICE_UUID);
static BLECharacteristic otaVersionChar(OTA_VERSION_UUID);
static BLECharacteristic otaVariantChar(OTA_VARIANT_UUID);

// ---------------------------------------------------------------------------
// Public API
// ---------------------------------------------------------------------------

void otaInit() {
    otaSvc.begin();

    // Version characteristic (read-only)
    // FIRMWARE_VERSION is substituted from "<dev>" by the CI pipeline.
    otaVersionChar.setProperties(CHR_PROPS_READ);
    otaVersionChar.setPermission(SECMODE_OPEN, SECMODE_NO_ACCESS);
    otaVersionChar.setMaxLen(16);
    otaVersionChar.begin();
    otaVersionChar.write(FIRMWARE_VERSION, strlen(FIRMWARE_VERSION));

    // Variant characteristic (read-only)
    // BOARD_VARIANT is set to "nrf52840" via -DBOARD_VARIANT in platformio.ini.
    otaVariantChar.setProperties(CHR_PROPS_READ);
    otaVariantChar.setPermission(SECMODE_OPEN, SECMODE_NO_ACCESS);
    otaVariantChar.setMaxLen(32);
    otaVariantChar.begin();
    otaVariantChar.write(BOARD_VARIANT, strlen(BOARD_VARIANT));
}
