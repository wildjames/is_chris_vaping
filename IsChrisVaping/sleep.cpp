#include "sleep.h"
#include "display.h"
#include "coils.h"
#include "bluetooth.h"
#include "ota.h"
#include <esp_sleep.h>

// Shared state
extern unsigned long lastActivityTime;

// Bitmask for ext1 wakeup: GPIO 12 and GPIO 14
#define COIL_WAKEUP_MASK ((1ULL << COIL_A_PIN) | (1ULL << COIL_B_PIN))

void sleepUpdate() {
  if (otaInProgress || coilAActive || coilBActive) return;
  if (millis() - lastActivityTime <= LIGHT_SLEEP_TIMEOUT_MS) return;

  // Wake when either coil pin goes HIGH
  esp_sleep_enable_ext1_wakeup(COIL_WAKEUP_MASK, ESP_EXT1_WAKEUP_ANY_HIGH);

  // Turn off display before sleeping
  analogWrite(LCD_BLK, 0);
  tft.writeCommand(ST77XX_DISPOFF);

  // Mark BLE as disconnected so any messages on wake get buffered
  deviceConnected = false;

  // Enter light sleep
  Serial.println("Entering light sleep...");
  Serial.flush();
  esp_light_sleep_start();

  // Woke from ext1 (coil activity)
  Serial.println("Light sleep wakeup (coil GPIO activity)");

  // Re-enable display
  tft.writeCommand(ST77XX_DISPON);
  analogWrite(LCD_BLK, LCD_BRIGHTNESS);

  // Let coilsUpdate() in main loop detect which coil is active
  lastActivityTime = millis();
}
