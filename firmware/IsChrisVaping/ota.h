#ifndef OTA_H
#define OTA_H

#include <BLEServer.h>
#include <BLECharacteristic.h>

// OTA BLE UUIDs
#define OTA_SERVICE_UUID        "fb1e4001-54ae-4a28-9f74-dfccb248601d"
#define OTA_CONTROL_UUID        "fb1e4002-54ae-4a28-9f74-dfccb248601d"
#define OTA_DATA_UUID           "fb1e4003-54ae-4a28-9f74-dfccb248601d"
#define OTA_VERSION_UUID        "fb1e4004-54ae-4a28-9f74-dfccb248601d"
#define OTA_VARIANT_UUID        "fb1e4005-54ae-4a28-9f74-dfccb248601d"

extern bool otaInProgress;

void otaInit(BLEServer* pServer);
void otaAbort();

#endif
