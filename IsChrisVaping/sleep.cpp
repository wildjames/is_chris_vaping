#include "sleep.h"
#include "display.h"
#include "coils.h"
#include "ota.h"
#include <esp_sleep.h>

// Shared state
extern unsigned long lastActivityTime;

// Sleep state (RTC-persisted across light sleep)
RTC_DATA_ATTR static unsigned long lightSleepStartTime = 0;
RTC_DATA_ATTR static bool inLightSleepPhase = false;

void sleepCheckWakeup() {
  esp_sleep_wakeup_cause_t wakeup_reason = esp_sleep_get_wakeup_cause();
  if (wakeup_reason == ESP_SLEEP_WAKEUP_EXT1) {
    Serial.println("Woke from sleep (coil activity detected)");
    inLightSleepPhase = false;
    lightSleepStartTime = 0;
  }
}

void sleepUpdate() {
  if (otaInProgress || coilAActive || coilBActive) return;
  if (millis() - lastActivityTime <= LIGHT_SLEEP_TIMEOUT_MS) return;

  // Configure ext1 wakeup on GPIO 12 or GPIO 14 going HIGH
  uint64_t wakeupPinMask = (1ULL << COIL_A_PIN) | (1ULL << COIL_B_PIN);
  esp_sleep_enable_ext1_wakeup(wakeupPinMask, ESP_EXT1_WAKEUP_ANY_HIGH);

  // Turn off display before sleeping
  analogWrite(LCD_BLK, 0);
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
