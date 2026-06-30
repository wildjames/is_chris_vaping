#include <esp_system.h>
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

  bluetoothInit();
  displayInit();
  coilsInit();

  // Show firmware version on power-on reset
  if (esp_reset_reason() == ESP_RST_POWERON) {
    showText(FIRMWARE_VERSION);
  }

  // Reset inactivity timer
  lastActivityTime = millis();

  Serial.printf("Firmware version: %s\n", FIRMWARE_VERSION);
  Serial.println("Serial commands: 1=CoilA start, 2=CoilA stop, 3=CoilB start, 4=CoilB stop");
  Serial.println();
}

void loop() {
  coilsUpdate();
  bluetoothUpdate();

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

  if (nameChanged) {
    nameChanged = false;
    drawVapeName();
  }

  // --- Sleep after inactivity ---
  sleepUpdate();

  // Allow breathing room for idle tasks (possibly not needed? two cores)
  delay(10);
}
