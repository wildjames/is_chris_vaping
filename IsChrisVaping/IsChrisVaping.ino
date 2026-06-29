#include <WiFi.h>
#include "version.h"
#include "display.h"
#include "bluetooth.h"
#include "ota.h"
#include "coils.h"
#include "sleep.h"

// Shared globals
unsigned long lastActivityTime = 0;
unsigned long notRippedTimerStart = 0;
bool notRippedTimerActive = false;

// NOT_RIPPED display timer
const unsigned long NOT_RIPPED_DELAY_MS = 3000;

void setup() {
  Serial.begin(115200);

  sleepCheckWakeup();

  // Disable WiFi to prevent GPIO2 conflict with display DC line
  WiFi.mode(WIFI_OFF);

  displayInit();
  coilsInit();

  // Reset inactivity timer
  lastActivityTime = millis();

  bluetoothInit();

  Serial.printf("Firmware version: %s\n", FIRMWARE_VERSION);
  Serial.println("Serial commands: 1=CoilA start, 2=CoilA stop, 3=CoilB start, 4=CoilB stop");
  Serial.println("60s inactivity -> light sleep (1hr), then deep sleep.");
  Serial.println();
}

void loop() {
  coilsUpdate();

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
    drawBtIcon();
  }

  // --- Sleep after inactivity ---
  sleepUpdate();

  delay(10);
}
