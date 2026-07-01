#include "ota.h"
#include "bluetooth.h"
#include <Update.h>
#include <BLE2902.h>

// Shared state
extern unsigned long lastActivityTime;

// OTA control commands (from phone)
#define OTA_CMD_BEGIN   0x01
#define OTA_CMD_END     0x02
#define OTA_CMD_ABORT   0x03

// OTA control responses (to phone)
#define OTA_RSP_READY   0x10
#define OTA_RSP_OK      0x11
#define OTA_RSP_ERROR   0x12
#define OTA_RSP_ACK     0x13

bool otaInProgress = false;
static uint32_t otaExpectedSize = 0;
static uint32_t otaReceivedSize = 0;
static uint32_t otaChunkCount = 0;
static const uint32_t OTA_ACK_INTERVAL = 50;
static BLECharacteristic* pOtaControl = NULL;
static BLECharacteristic* pOtaData = NULL;
static BLECharacteristic* pOtaVersion = NULL;

void otaAbort() {
  if (otaInProgress) {
    Update.abort();
    otaInProgress = false;
    otaReceivedSize = 0;
  }
}

class OtaControlCallbacks : public BLECharacteristicCallbacks {
  void onWrite(BLECharacteristic* pCharacteristic) {
    const uint8_t* data = pCharacteristic->getData();
    size_t len = pCharacteristic->getLength();
    if (!data || len < 1) return;

    uint8_t cmd = data[0];
    uint8_t response[2];

    lastActivityTime = millis();

    switch (cmd) {
      case OTA_CMD_BEGIN: {
        if (len < 5) {
          response[0] = OTA_RSP_ERROR;
          response[1] = 0x01; // invalid length
          pCharacteristic->setValue(response, 2);
          pCharacteristic->notify();
          return;
        }
        // Extract 4-byte file size (little-endian)
        otaExpectedSize = (uint32_t)data[1] |
                          ((uint32_t)data[2] << 8) |
                          ((uint32_t)data[3] << 16) |
                          ((uint32_t)data[4] << 24);
        otaReceivedSize = 0;
        otaChunkCount = 0;

        Serial.printf("OTA begin: expecting %u bytes\n", otaExpectedSize);

        if (!Update.begin(otaExpectedSize)) {
          Serial.println("OTA Update.begin() failed");
          response[0] = OTA_RSP_ERROR;
          response[1] = 0x02; // begin failed
          pCharacteristic->setValue(response, 2);
          pCharacteristic->notify();
          return;
        }

        otaInProgress = true;
        response[0] = OTA_RSP_READY;
        pCharacteristic->setValue(response, 1);
        pCharacteristic->notify();
        Serial.println("OTA ready for data");
        break;
      }

      case OTA_CMD_END: {
        if (!otaInProgress) {
          response[0] = OTA_RSP_ERROR;
          response[1] = 0x03; // not in progress
          pCharacteristic->setValue(response, 2);
          pCharacteristic->notify();
          return;
        }

        Serial.printf("OTA end: received %u / %u bytes\n", otaReceivedSize, otaExpectedSize);
        if (otaReceivedSize != otaExpectedSize) {
          Serial.printf("OTA size mismatch! Aborting.\n");
          Update.abort();
          otaInProgress = false;
          response[0] = OTA_RSP_ERROR;
          response[1] = 0x06; // size mismatch
          pCharacteristic->setValue(response, 2);
          pCharacteristic->notify();
          return;
        }

        if (Update.end(false)) {
          Serial.println("OTA success! Rebooting...");
          response[0] = OTA_RSP_OK;
          pCharacteristic->setValue(response, 1);
          pCharacteristic->notify();
          delay(500);
          ESP.restart();
        } else {
          Serial.printf("OTA end failed: %s\n", Update.errorString());
          response[0] = OTA_RSP_ERROR;
          response[1] = 0x04; // end failed
          pCharacteristic->setValue(response, 2);
          pCharacteristic->notify();
          otaInProgress = false;
        }
        break;
      }

      case OTA_CMD_ABORT: {
        otaAbort();
        Serial.println("OTA aborted by client");
        response[0] = OTA_RSP_OK;
        pCharacteristic->setValue(response, 1);
        pCharacteristic->notify();
        break;
      }
    }
  }
};

class OtaDataCallbacks : public BLECharacteristicCallbacks {
  void onWrite(BLECharacteristic* pCharacteristic) {
    if (!otaInProgress) return;

    const uint8_t* data = pCharacteristic->getData();
    size_t len = pCharacteristic->getLength();
    if (!data || len == 0) return;

    size_t written = Update.write(const_cast<uint8_t*>(data), len);
    if (written != len) {
      Serial.printf("OTA write error: wrote %d of %d\n", written, len);
      // Notify error via control characteristic
      uint8_t response[2] = { OTA_RSP_ERROR, 0x05 };
      pOtaControl->setValue(response, 2);
      pOtaControl->notify();
      Update.abort();
      otaInProgress = false;
      return;
    }

    otaReceivedSize += len;
    otaChunkCount++;

    // Send ACK with byte count every N chunks for flow control
    if (otaChunkCount % OTA_ACK_INTERVAL == 0) {
      uint8_t ack[5];
      ack[0] = OTA_RSP_ACK;
      ack[1] = (uint8_t)(otaReceivedSize & 0xFF);
      ack[2] = (uint8_t)((otaReceivedSize >> 8) & 0xFF);
      ack[3] = (uint8_t)((otaReceivedSize >> 16) & 0xFF);
      ack[4] = (uint8_t)((otaReceivedSize >> 24) & 0xFF);
      Serial.printf("OTA ACK: %u / %u bytes\n", otaReceivedSize, otaExpectedSize);
      pOtaControl->setValue(ack, 5);
      pOtaControl->notify();
    }
  }
};

void otaInit(BLEServer* pServer) {
  BLEService* pOtaService = pServer->createService(OTA_SERVICE_UUID);

  // OTA Control Characteristic (write + notify)
  static OtaControlCallbacks controlCallbacks;
  pOtaControl = pOtaService->createCharacteristic(
    OTA_CONTROL_UUID,
    BLECharacteristic::PROPERTY_WRITE |
    BLECharacteristic::PROPERTY_NOTIFY
  );
  pOtaControl->setCallbacks(&controlCallbacks);
  pOtaControl->addDescriptor(new BLE2902());

  // OTA Data Characteristic (write without response for speed, with response as fallback)
  static OtaDataCallbacks dataCallbacks;
  pOtaData = pOtaService->createCharacteristic(
    OTA_DATA_UUID,
    BLECharacteristic::PROPERTY_WRITE | BLECharacteristic::PROPERTY_WRITE_NR
  );
  pOtaData->setCallbacks(&dataCallbacks);

  // OTA Version Characteristic (read-only)
  pOtaVersion = pOtaService->createCharacteristic(
    OTA_VERSION_UUID,
    BLECharacteristic::PROPERTY_READ
  );
  pOtaVersion->setValue(FIRMWARE_VERSION);

  // OTA Variant Characteristic (read-only) - tells the app which firmware binary to fetch
  BLECharacteristic* pOtaVariant = pOtaService->createCharacteristic(
    OTA_VARIANT_UUID,
    BLECharacteristic::PROPERTY_READ
  );
  // This is the DBOARD_VARIANT macro defined in the platformio.ini build flags
  pOtaVariant->setValue(BOARD_VARIANT);

  pOtaService->start();
}
