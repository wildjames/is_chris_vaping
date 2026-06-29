#include <WiFi.h>
#include <BLEDevice.h>
#include <BLEServer.h>
#include <BLEUtils.h>
#include <BLE2902.h>
#include <Update.h>
#include <Button.h>
#include <Adafruit_GFX.h>
#include <Adafruit_ST7789.h>

#define FIRMWARE_VERSION "1.1.3"

#include "bluetooth_connected.h"
#include "bluetooth_disconnected.h"

// LCD pins
#define LCD_MOSI 23
#define LCD_SCLK 18
#define LCD_CS   15
#define LCD_DC    2
#define LCD_RST   4
#define LCD_BLK  32
#define LCD_BRIGHTNESS 25

Adafruit_ST7789 tft = Adafruit_ST7789(LCD_CS, LCD_DC, LCD_RST);

// Coil sensing pins
const int COIL_A_PIN = 12;
const int COIL_B_PIN = 14;

// Voltage threshold for detecting a draw
// With 2:1 voltage divider: 4V coil -> 2V at pin, 1.2V check -> 0.6V at pin
// Threshold at ~1.2V (midpoint) = 1365 ADC counts (11dB attenuation, 0-3.6V range)
const int DRAW_THRESHOLD = 1365;

// Debounce: coil must be above threshold for this many consecutive reads
const int DEBOUNCE_COUNT = 5;

// Coil state tracking
bool coilAActive = false;
bool coilBActive = false;
int coilACount = 0;
int coilBCount = 0;

// NOT_RIPPED display timer
const unsigned long NOT_RIPPED_DELAY_MS = 3000;
unsigned long notRippedTimerStart = 0;
bool notRippedTimerActive = false;

// Current display text (for redraw on BT status change)
const char* currentDisplayText = "NOT\nRIPPED";

// Sleep timing
const unsigned long LIGHT_SLEEP_TIMEOUT_MS = 60000;       // 60s inactivity -> light sleep
const unsigned long DEEP_SLEEP_TIMEOUT_MS = 3600000;       // 1 hour in light sleep -> deep sleep
unsigned long lastActivityTime = 0;
RTC_DATA_ATTR unsigned long lightSleepStartTime = 0;
RTC_DATA_ATTR bool inLightSleepPhase = false;

// UUIDs for BLE service and characteristic
#define SERVICE_UUID        "189a9192-f68f-4ac4-962e-d70e7c3755a0"
#define CHARACTERISTIC_UUID "5cf4a205-84e1-42ad-ac23-e5adc776a992"

// OTA BLE UUIDs
#define OTA_SERVICE_UUID        "fb1e4001-54ae-4a28-9f74-dfccb248601d"
#define OTA_CONTROL_UUID        "fb1e4002-54ae-4a28-9f74-dfccb248601d"
#define OTA_DATA_UUID           "fb1e4003-54ae-4a28-9f74-dfccb248601d"
#define OTA_VERSION_UUID        "fb1e4004-54ae-4a28-9f74-dfccb248601d"

// OTA control commands (from phone)
#define OTA_CMD_BEGIN   0x01
#define OTA_CMD_END     0x02
#define OTA_CMD_ABORT   0x03

// OTA control responses (to phone)
#define OTA_RSP_READY   0x10
#define OTA_RSP_OK      0x11
#define OTA_RSP_ERROR   0x12
#define OTA_RSP_ACK     0x13

BLEServer* pServer = NULL;
BLECharacteristic* pCharacteristic = NULL;
BLECharacteristic* pOtaControl = NULL;
BLECharacteristic* pOtaData = NULL;
BLECharacteristic* pOtaVersion = NULL;
bool deviceConnected = false;
bool previousConnected = false;
bool otaInProgress = false;
uint32_t otaExpectedSize = 0;
uint32_t otaReceivedSize = 0;

// BLE message definitions
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
      Update.abort();
      otaInProgress = false;
      otaReceivedSize = 0;
      Serial.println("OTA aborted due to disconnect");
    }
    // Restart advertising so phone can reconnect
    pServer->startAdvertising();
  }
};

// OTA Control Characteristic callback
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
        if (otaInProgress) {
          Update.abort();
          otaInProgress = false;
          otaReceivedSize = 0;
          Serial.println("OTA aborted by client");
        }
        response[0] = OTA_RSP_OK;
        pCharacteristic->setValue(response, 1);
        pCharacteristic->notify();
        break;
      }
    }
  }
};

// OTA Data Characteristic callback
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
    // Only write progress every 50 chunks
    if (otaReceivedSize % (50 * len) < len) {
      Serial.printf("OTA received: %u / %u bytes\n", otaReceivedSize, otaExpectedSize);
    }
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

// Draw the bluetooth icon in the upper-left corner
void drawBtIcon() {
  const uint8_t* btBitmap = deviceConnected ? bluetooth_connected : bluetooth_disconnected;
  uint16_t w = bluetooth_connected_width;
  uint16_t h = bluetooth_connected_height;

  // Clear the icon area and draw the new icon
  tft.fillRect(0, 0, w + 2, h + 2, ST77XX_BLACK);
  tft.drawBitmap(1, 1, btBitmap, w, h, ST77XX_WHITE);
}

// Draw centered multi-line text on screen with BT icon overlay
void showText(const char* text) {
  currentDisplayText = text;

  tft.fillScreen(ST77XX_BLACK);

  // At textSize=7: 42px wide, 56px tall per char - closest to 170/3 approx. 57px
  const uint8_t textSize = 6;
  const uint8_t charW = 6 * textSize;  // 42
  const uint8_t charH = 8 * textSize;  // 56
  const uint8_t lineSpacing = 2;

  // Count lines and find max line length
  uint8_t lineCount = 1;
  const char* p = text;
  while (*p) { if (*p == '\n') lineCount++; p++; }

  // Calculate total text block height
  uint16_t totalH = lineCount * charH + (lineCount - 1) * lineSpacing;
  int16_t startY = (170 - totalH) / 2;

  tft.setTextSize(textSize);
  tft.setTextColor(ST77XX_WHITE);
  tft.setTextWrap(false);

  // Draw each line centered
  const char* lineStart = text;
  for (uint8_t line = 0; line < lineCount; line++) {
    // Find end of this line
    const char* lineEnd = lineStart;
    while (*lineEnd && *lineEnd != '\n') lineEnd++;
    uint8_t lineLen = lineEnd - lineStart;

    int16_t x = (320 - lineLen * charW) / 2;
    int16_t y = startY + line * (charH + lineSpacing);

    tft.setCursor(x, y);
    for (uint8_t i = 0; i < lineLen; i++) {
      tft.write(lineStart[i]);
    }

    lineStart = (*lineEnd == '\n') ? lineEnd + 1 : lineEnd;
  }

  drawBtIcon();
}

void handleCoilAStarted() {
  notRippedTimerActive = false;
  coilAActive = true;
  lastActivityTime = millis();
  sendBLEMessage(MSG_COIL_A_STARTED);
  showText("RIPPIN'\nCOIL A");
}

void handleCoilAStopped() {
  coilAActive = false;
  lastActivityTime = millis();
  sendBLEMessage(MSG_COIL_A_STOPPED);
  showText("QUIT\nRIPPIN' A");
  notRippedTimerStart = millis();
  notRippedTimerActive = true;
}

void handleCoilBStarted() {
  coilBActive = true;
  notRippedTimerActive = false;
  lastActivityTime = millis();
  sendBLEMessage(MSG_COIL_B_STARTED);
  showText("RIPPIN'\nCOIL B");
}

void handleCoilBStopped() {
  coilBActive = false;
  lastActivityTime = millis();
  sendBLEMessage(MSG_COIL_B_STOPPED);
  showText("QUIT\nRIPPIN' B");
  notRippedTimerStart = millis();
  notRippedTimerActive = true;
}

void setup() {
  Serial.begin(115200);

  // Check wakeup reason
  esp_sleep_wakeup_cause_t wakeup_reason = esp_sleep_get_wakeup_cause();
  if (wakeup_reason == ESP_SLEEP_WAKEUP_EXT1) {
    Serial.println("Woke from sleep (coil activity detected)");
    // Activity detected - reset light sleep phase
    inLightSleepPhase = false;
    lightSleepStartTime = 0;
  }

  // Disable WiFi to prevent GPIO2 conflict with display DC line
  WiFi.mode(WIFI_OFF);

  // Initialize LCD
  pinMode(LCD_BLK, OUTPUT);
  analogWrite(LCD_BLK, LCD_BRIGHTNESS);
  tft.init(170, 320);
  tft.writeCommand(ST77XX_DISPON);
  tft.setRotation(1);
  tft.setSPISpeed(80000000);  // 80MHz SPI
  tft.fillScreen(ST77XX_BLACK);
  showText("NOT\nRIPPED");

  // Configure ADC for coil sensing pins
  analogSetAttenuation(ADC_11db);
  pinMode(COIL_A_PIN, INPUT);
  pinMode(COIL_B_PIN, INPUT);

  // Reset inactivity timer
  lastActivityTime = millis();

  Serial.println("Starting BLE...");

  // Initialize BLE
  BLEDevice::init("IsChrisVaping");

  // Create BLE Server
  pServer = BLEDevice::createServer();
  pServer->setCallbacks(new MyServerCallbacks());

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

  // Create OTA BLE Service
  BLEService* pOtaService = pServer->createService(OTA_SERVICE_UUID);

  // OTA Control Characteristic (write + notify)
  pOtaControl = pOtaService->createCharacteristic(
    OTA_CONTROL_UUID,
    BLECharacteristic::PROPERTY_WRITE |
    BLECharacteristic::PROPERTY_NOTIFY
  );
  pOtaControl->setCallbacks(new OtaControlCallbacks());
  pOtaControl->addDescriptor(new BLE2902());

  // OTA Data Characteristic (write without response for speed, with response as fallback)
  pOtaData = pOtaService->createCharacteristic(
    OTA_DATA_UUID,
    BLECharacteristic::PROPERTY_WRITE | BLECharacteristic::PROPERTY_WRITE_NR
  );
  pOtaData->setCallbacks(new OtaDataCallbacks());

  // OTA Version Characteristic (read-only)
  pOtaVersion = pOtaService->createCharacteristic(
    OTA_VERSION_UUID,
    BLECharacteristic::PROPERTY_READ
  );
  pOtaVersion->setValue(FIRMWARE_VERSION);

  pOtaService->start();

  // Start advertising
  BLEAdvertising* pAdvertising = BLEDevice::getAdvertising();
  pAdvertising->addServiceUUID(SERVICE_UUID);
  pAdvertising->addServiceUUID(OTA_SERVICE_UUID);
  pAdvertising->setScanResponse(true);
  pAdvertising->setMinPreferred(0x06);
  pAdvertising->setMaxPreferred(0x12);
  BLEDevice::startAdvertising();

  Serial.println("BLE ready. Waiting for connection...");
  Serial.print("Running firmware version ");
  Serial.println(FIRMWARE_VERSION);
  Serial.println("Serial commands: 1=CoilA start, 2=CoilA stop, 3=CoilB start, 4=CoilB stop");
  Serial.println("60s inactivity -> light sleep (1hr), then deep sleep.");
  Serial.println();
}

void loop() {
  // // --- Coil A detection ---
  // int coilAReading = analogRead(COIL_A_PIN);
  // if (coilAReading > DRAW_THRESHOLD) {
  //   if (coilACount < DEBOUNCE_COUNT) coilACount++;
  //   if (coilACount >= DEBOUNCE_COUNT && !coilAActive) {
  //     coilAActive = true;
  //     lastActivityTime = millis();
  //     Serial.print("Coil A senses ");
  //     Serial.println(coilAReading);
  //     handleCoilAStarted();
  //   }
  // } else {
  //   if (coilACount > 0) coilACount--;
  //   if (coilACount == 0 && coilAActive) {
  //     coilAActive = false;
  //     lastActivityTime = millis();
  //     handleCoilAStopped();
  //   }
  // }

  // // --- Coil B detection ---
  // int coilBReading = analogRead(COIL_B_PIN);
  // if (coilBReading > DRAW_THRESHOLD) {
  //   if (coilBCount < DEBOUNCE_COUNT) coilBCount++;
  //   if (coilBCount >= DEBOUNCE_COUNT && !coilBActive) {
  //     coilBActive = true;
  //     lastActivityTime = millis();
  //     Serial.print("Coil B senses ");
  //     Serial.println(coilBReading);
  //     handleCoilBStarted();
  //   }
  // } else {
  //   if (coilBCount > 0) coilBCount--;
  //   if (coilBCount == 0 && coilBActive) {
  //     coilBActive = false;
  //     lastActivityTime = millis();
  //     handleCoilBStopped();
  //   }
  // }

  // --- Serial commands for testing ---
  if (Serial.available()) {
    char input = Serial.read();

    switch (input) {
      case '1':
        handleCoilAStarted();
        break;
      case '2':
        handleCoilAStopped();
        break;
      case '3':
        handleCoilBStarted();
        break;
      case '4':
        handleCoilBStopped();
        break;
    }
  }

  // --- NOT_RIPPED timer ---
  if (notRippedTimerActive && (millis() - notRippedTimerStart >= NOT_RIPPED_DELAY_MS)) {
    notRippedTimerActive = false;
    showText("NOT\nRIPPED");
  }

  // --- Bluetooth connection status change ---
  if (deviceConnected != previousConnected) {
    previousConnected = deviceConnected;
    // Just redraw the BT icon without clearing the screen
    drawBtIcon();
  }

  // --- Sleep after inactivity ---
  if (!otaInProgress && !coilAActive && !coilBActive && (millis() - lastActivityTime > LIGHT_SLEEP_TIMEOUT_MS)) {
    // Configure ext1 wakeup on GPIO 12 or GPIO 14 going HIGH
    uint64_t wakeupPinMask = (1ULL << COIL_A_PIN) | (1ULL << COIL_B_PIN);
    esp_sleep_enable_ext1_wakeup(wakeupPinMask, ESP_EXT1_WAKEUP_ANY_HIGH);

    // Pin the tft brightness to 0 before sleeping
    analogWrite(LCD_BLK, 0);
    // and disable the display to save power
    tft.writeCommand(ST77XX_DISPOFF);

    // Track how long we've been in the light sleep phase
    if (!inLightSleepPhase) {
      inLightSleepPhase = true;
      lightSleepStartTime = millis();
    }

    unsigned long lightSleepElapsed = millis() - lightSleepStartTime;

    if (lightSleepElapsed >= DEEP_SLEEP_TIMEOUT_MS) {
      // Been in light sleep phase for 1 hour - switch to deep sleep
      Serial.println("Entering deep sleep (1hr light sleep elapsed)...");
      Serial.flush();
      esp_deep_sleep_start();
    } else {
      // Light sleep - wake on ext1
      Serial.println("Entering light sleep...");
      Serial.flush();
      esp_light_sleep_start();
      // Execution resumes here after light sleep wakeup
      Serial.println("Light sleep wakeup");
      lastActivityTime = millis() - LIGHT_SLEEP_TIMEOUT_MS;  // Stay in sleep cycle unless coil triggers
    }
  }

  delay(10);
}
