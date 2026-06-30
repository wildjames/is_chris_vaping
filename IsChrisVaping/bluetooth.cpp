#include "bluetooth.h"
#include "ota.h"
#include <Preferences.h>

BLEServer* pServer = NULL;
BLECharacteristic* pCharacteristic = NULL;
BLECharacteristic* pNameCharacteristic = NULL;
bool deviceConnected = false;
bool previousConnected = false;

char vapeName[MAX_VAPE_NAME_LEN + 1] = DEFAULT_VAPE_NAME;
bool nameChanged = false;

static Preferences prefs;

const char* MSG_COIL_A_STARTED = "COIL_A:STARTED";
const char* MSG_COIL_A_STOPPED = "COIL_A:STOPPED";
const char* MSG_COIL_B_STARTED = "COIL_B:STARTED";
const char* MSG_COIL_B_STOPPED = "COIL_B:STOPPED";

// Circular buffer for messages when BLE is not connected
static char msgBuffer[MSG_BUFFER_SIZE][MSG_MAX_LEN];
// Index of the head of the buffer (oldest message)
static int msgBufferHead = 0;
// Count of messages currently in the buffer
static int msgBufferCount = 0;

// Pending flush state
bool pendingFlush = false;
unsigned long flushAfterMs = 0;

// Forward declaration
void flushBLEBuffer();

void loadVapeName() {
  prefs.begin("vape", false);  // read-write in case we need to generate a default
  String name = prefs.getString("name", "");
  if (name.length() == 0) {
    // First boot: generate a unique default name with 4 random digits
    char defaultName[MAX_VAPE_NAME_LEN + 1];
    int suffix = random(0, 10000);
    snprintf(defaultName, sizeof(defaultName), "%s %04d", DEFAULT_VAPE_NAME, suffix);
    prefs.putString("name", defaultName);
    strncpy(vapeName, defaultName, MAX_VAPE_NAME_LEN);
    vapeName[MAX_VAPE_NAME_LEN] = '\0';
    Serial.printf("Generated default vape name: %s\n", vapeName);
  } else {
    strncpy(vapeName, name.c_str(), MAX_VAPE_NAME_LEN);
    vapeName[MAX_VAPE_NAME_LEN] = '\0';
    Serial.printf("Loaded vape name: %s\n", vapeName);
  }
  prefs.end();
}

void saveVapeName(const char* name) {
  strncpy(vapeName, name, MAX_VAPE_NAME_LEN);
  vapeName[MAX_VAPE_NAME_LEN] = '\0';
  prefs.begin("vape", false);  // read-write
  prefs.putString("name", vapeName);
  prefs.end();
  Serial.printf("Saved vape name: %s\n", vapeName);
  nameChanged = true;
}

class NameCharacteristicCallbacks : public BLECharacteristicCallbacks {
  void onWrite(BLECharacteristic* pChar) {
    String value = pChar->getValue();
    if (value.length() > 0 && value.length() <= MAX_VAPE_NAME_LEN) {
      saveVapeName(value.c_str());
      Serial.printf("Name updated via BLE: %s\n", vapeName);
    }
  }
};

class MyServerCallbacks : public BLEServerCallbacks {
  void onConnect(BLEServer* pServer) {
    deviceConnected = true;
    Serial.println("Device connected");
    BLEDevice::getAdvertising()->stop();
    // Schedule flush after delay to allow client to subscribe to notifications
    if (msgBufferCount > 0) {
      pendingFlush = true;
      flushAfterMs = millis() + FLUSH_DELAY_MS;
    }
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

static void bufferBLEMessage(const char* msg) {
  int idx = (msgBufferHead + msgBufferCount) % MSG_BUFFER_SIZE;
  if (msgBufferCount >= MSG_BUFFER_SIZE) {
    // Buffer full - overwrite oldest
    msgBufferHead = (msgBufferHead + 1) % MSG_BUFFER_SIZE;
  } else {
    msgBufferCount++;
  }
  strncpy(msgBuffer[idx], msg, MSG_MAX_LEN - 1);
  msgBuffer[idx][MSG_MAX_LEN - 1] = '\0';
  Serial.printf("Buffered message (%d in buffer): %s\n", msgBufferCount, msg);
}

void flushBLEBuffer() {
  if (msgBufferCount == 0) return;
  Serial.printf("Flushing %d buffered messages\n", msgBufferCount);
  while (msgBufferCount > 0) {
    pCharacteristic->setValue(msgBuffer[msgBufferHead]);
    pCharacteristic->notify();
    Serial.printf("Flushed: %s\n", msgBuffer[msgBufferHead]);
    msgBufferHead = (msgBufferHead + 1) % MSG_BUFFER_SIZE;
    msgBufferCount--;
    delay(20);  // Small delay between notifications to avoid congestion
  }
  msgBufferHead = 0;
}

void bluetoothUpdate() {
  if (pendingFlush && deviceConnected && millis() >= flushAfterMs) {
    pendingFlush = false;
    flushBLEBuffer();
  }
}

void sendBLEMessage(const char* msg) {
  if (deviceConnected) {
    pCharacteristic->setValue(msg);
    pCharacteristic->notify();
    Serial.print("Sent: ");
    Serial.println(msg);
  } else {
    bufferBLEMessage(msg);
  }
}

void bluetoothInit() {
  Serial.println("Starting BLE...");

  // Load the device name from flash
  loadVapeName();

  BLEDevice::init("IsChrisVaping");

  // Create BLE Server
  static MyServerCallbacks serverCallbacks;
  pServer = BLEDevice::createServer();
  pServer->setCallbacks(&serverCallbacks);

  // Create BLE Service
  BLEService* pService = pServer->createService(BLEUUID(SERVICE_UUID), 20);

  // Create BLE Characteristic with notify property (coil data)
  pCharacteristic = pService->createCharacteristic(
    CHARACTERISTIC_UUID,
    BLECharacteristic::PROPERTY_READ |
    BLECharacteristic::PROPERTY_NOTIFY
  );
  pCharacteristic->addDescriptor(new BLE2902());
  pCharacteristic->setValue("READY");

  // Create Name Characteristic (read + write)
  static NameCharacteristicCallbacks nameCallbacks;
  pNameCharacteristic = pService->createCharacteristic(
    NAME_CHARACTERISTIC_UUID,
    BLECharacteristic::PROPERTY_READ |
    BLECharacteristic::PROPERTY_WRITE
  );
  pNameCharacteristic->setCallbacks(&nameCallbacks);
  pNameCharacteristic->setValue(vapeName);

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
