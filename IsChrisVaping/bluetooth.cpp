#include "bluetooth.h"
#include "ota.h"

BLEServer* pServer = NULL;
BLECharacteristic* pCharacteristic = NULL;
bool deviceConnected = false;
bool previousConnected = false;

const char* MSG_COIL_A_STARTED = "COIL_A:STARTED";
const char* MSG_COIL_A_STOPPED = "COIL_A:STOPPED";
const char* MSG_COIL_B_STARTED = "COIL_B:STARTED";
const char* MSG_COIL_B_STOPPED = "COIL_B:STOPPED";

class MyServerCallbacks : public BLEServerCallbacks {
  void onConnect(BLEServer* pServer) {
    deviceConnected = true;
    Serial.println("Device connected");
    BLEDevice::getAdvertising()->stop();
  }

  void onDisconnect(BLEServer* pServer) {
    deviceConnected = false;
    Serial.println("Device disconnected");
    // Abort any in-progress OTA on disconnect
    if (otaInProgress) {
      otaAbort();
      Serial.println("OTA aborted due to disconnect");
    }
    // Restart advertising so phone can reconnect
    pServer->startAdvertising();
  }
};

void sendBLEMessage(const char* msg) {
  if (deviceConnected) {
    pCharacteristic->setValue(msg);
    pCharacteristic->notify();
    Serial.print("Sent: ");
    Serial.println(msg);
  } else {
    Serial.print("No device connected. Would send: ");
    Serial.println(msg);
  }
}

void bluetoothInit() {
  Serial.println("Starting BLE...");

  BLEDevice::init("IsChrisVaping");

  // Create BLE Server
  static MyServerCallbacks serverCallbacks;
  pServer = BLEDevice::createServer();
  pServer->setCallbacks(&serverCallbacks);

  // Create BLE Service
  BLEService* pService = pServer->createService(SERVICE_UUID);

  // Create BLE Characteristic with notify property
  pCharacteristic = pService->createCharacteristic(
    CHARACTERISTIC_UUID,
    BLECharacteristic::PROPERTY_READ |
    BLECharacteristic::PROPERTY_NOTIFY
  );
  pCharacteristic->addDescriptor(new BLE2902());
  pCharacteristic->setValue("READY");

  // Start the service
  pService->start();

  // Setup OTA service
  otaInit(pServer);

  // Start advertising
  BLEAdvertising* pAdvertising = BLEDevice::getAdvertising();
  pAdvertising->addServiceUUID(SERVICE_UUID);
  pAdvertising->addServiceUUID(OTA_SERVICE_UUID);
  pAdvertising->setScanResponse(true);
  pAdvertising->setMinPreferred(0x06);
  pAdvertising->setMaxPreferred(0x12);
  BLEDevice::startAdvertising();

  Serial.println("BLE ready. Waiting for connection...");
}
