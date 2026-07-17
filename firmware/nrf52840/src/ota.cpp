#include "ota.h"
#include "version.h"
#include <bluefruit.h>

// Read-only info service: exposes firmware version so the companion app can
// determine whether a Nordic DFU update is needed.
// The actual OTA transfer is handled by the BLEDfu service (Nordic DFU
// protocol), which is initialised in bluetooth.cpp.

static BLEService        otaSvc(OTA_SERVICE_UUID);
static BLECharacteristic otaVersionChar(OTA_VERSION_UUID);

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
}
