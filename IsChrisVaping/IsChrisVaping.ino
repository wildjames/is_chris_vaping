#include <WiFi.h>
#include <BLEDevice.h>
#include <BLEServer.h>
#include <BLEUtils.h>
#include <BLE2902.h>
#include <Button.h>
#include <Adafruit_GFX.h>
#include <Adafruit_ST7789.h>

#include "RIPPING_COIL_A.h"
#include "RIPPING_COIL_B.h"
#include "QUITTING_RIPPING_COIL_A.h"
#include "QUITTING_RIPPING_COIL_B.h"
#include "NOT_RIPPED.h"
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

// Sleep timing
const unsigned long LIGHT_SLEEP_TIMEOUT_MS = 60000;       // 60s inactivity -> light sleep
const unsigned long DEEP_SLEEP_TIMEOUT_MS = 3600000;       // 1 hour in light sleep -> deep sleep
unsigned long lastActivityTime = 0;
RTC_DATA_ATTR unsigned long lightSleepStartTime = 0;
RTC_DATA_ATTR bool inLightSleepPhase = false;

// UUIDs for BLE service and characteristic
#define SERVICE_UUID        "189a9192-f68f-4ac4-962e-d70e7c3755a0"
#define CHARACTERISTIC_UUID "5cf4a205-84e1-42ad-ac23-e5adc776a992"

BLEServer* pServer = NULL;
BLECharacteristic* pCharacteristic = NULL;
bool deviceConnected = false;
bool previousConnected = false;

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

// Line buffer for converting 1-bit bitmap to RGB565 one row at a time
static uint16_t lineBuf[170];

void showImage(const uint8_t* bitmap, uint16_t w, uint16_t h) {
  // Every image is OR'd with the bluetooth status icon
  const uint8_t* btBitmap = deviceConnected ? bluetooth_connected : bluetooth_disconnected;

  tft.startWrite();
  tft.setAddrWindow(0, 0, w, h);

  uint32_t totalPixels = (uint32_t)w * h;
  for (uint32_t i = 0; i < totalPixels; i += w) {
    for (uint16_t x = 0; x < w; x++) {
      uint32_t idx = i + x;
      uint8_t mainBit = (pgm_read_byte(&bitmap[idx / 8]) >> (7 - (idx & 7))) & 1;
      uint8_t btBit = (pgm_read_byte(&btBitmap[idx / 8]) >> (7 - (idx & 7))) & 1;
      lineBuf[x] = (mainBit || btBit) ? 0xFFFF : 0x0000;
    }
    tft.writePixels(lineBuf, w);
  }

  tft.endWrite();
}

void handleCoilAStarted() {
  notRippedTimerActive = false;
  coilAActive = true;
  lastActivityTime = millis();
  sendBLEMessage(MSG_COIL_A_STARTED);
  showImage(RIPPING_COIL_A, RIPPING_COIL_A_width, RIPPING_COIL_A_height);
}

void handleCoilAStopped() {
  coilAActive = false;
  lastActivityTime = millis();
  sendBLEMessage(MSG_COIL_A_STOPPED);
  showImage(QUITTING_RIPPING_COIL_A, QUITTING_RIPPING_COIL_A_width, QUITTING_RIPPING_COIL_A_height);
  notRippedTimerStart = millis();
  notRippedTimerActive = true;
}

void handleCoilBStarted() {
  coilBActive = true;
  notRippedTimerActive = false;
  lastActivityTime = millis();
  sendBLEMessage(MSG_COIL_B_STARTED);
  showImage(RIPPING_COIL_B, RIPPING_COIL_B_width, RIPPING_COIL_B_height);
}

void handleCoilBStopped() {
  coilBActive = false;
  lastActivityTime = millis();
  sendBLEMessage(MSG_COIL_B_STOPPED);
  showImage(QUITTING_RIPPING_COIL_B, QUITTING_RIPPING_COIL_B_width, QUITTING_RIPPING_COIL_B_height);
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
  tft.setRotation(0);
  tft.setSPISpeed(80000000);  // 80MHz SPI for fast screen updates
  tft.fillScreen(ST77XX_BLACK);
  showImage(NOT_RIPPED, NOT_RIPPED_width, NOT_RIPPED_height);

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

  // Start advertising
  BLEAdvertising* pAdvertising = BLEDevice::getAdvertising();
  pAdvertising->addServiceUUID(SERVICE_UUID);
  pAdvertising->setScanResponse(true);
  pAdvertising->setMinPreferred(0x06);
  pAdvertising->setMaxPreferred(0x12);
  BLEDevice::startAdvertising();

  Serial.println("BLE ready. Waiting for connection...");
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
    showImage(NOT_RIPPED, NOT_RIPPED_width, NOT_RIPPED_height);
  }

  // --- Bluetooth connection status change ---
  if (deviceConnected != previousConnected) {
    previousConnected = deviceConnected;
    // Redraw current screen to update bluetooth icon
    if (!coilAActive && !coilBActive && !notRippedTimerActive) {
      showImage(NOT_RIPPED, NOT_RIPPED_width, NOT_RIPPED_height);
    }
  }

  // --- Sleep after inactivity ---
  if (!coilAActive && !coilBActive && (millis() - lastActivityTime > LIGHT_SLEEP_TIMEOUT_MS)) {
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
