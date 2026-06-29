#include "sleep.h"
#include "display.h"
#include "coils.h"
#include "ota.h"
#include <esp_sleep.h>

// Shared state
extern unsigned long lastActivityTime;

static bool stayAsleep = false;

void sleepCheckWakeup() {
  esp_sleep_wakeup_cause_t wakeup_reason = esp_sleep_get_wakeup_cause();
  if (wakeup_reason == ESP_SLEEP_WAKEUP_EXT1) {
    Serial.println("Woke from sleep (coil activity detected)");
    stayAsleep = false;
  }
}

void sleepUpdate() {
  if (otaInProgress || coilAActive || coilBActive) return;
  if (!stayAsleep && (millis() - lastActivityTime <= LIGHT_SLEEP_TIMEOUT_MS)) return;

  // Configure ext1 wakeup on GPIO 12 or GPIO 14 going HIGH
  uint64_t wakeupPinMask = (1ULL << COIL_A_PIN) | (1ULL << COIL_B_PIN);
  esp_sleep_enable_ext1_wakeup(wakeupPinMask, ESP_EXT1_WAKEUP_ANY_HIGH);

  // Also wake on timer so we can transition to deep sleep
  esp_sleep_enable_timer_wakeup((uint64_t)DEEP_SLEEP_TIMEOUT_MS * 1000ULL);

  // Turn off display before sleeping
  analogWrite(LCD_BLK, 0);
  tft.writeCommand(ST77XX_DISPOFF);

  // Enter light sleep
  Serial.println("Entering light sleep...");
  Serial.flush();
  esp_light_sleep_start();

  // Execution resumes here after wakeup
  esp_sleep_wakeup_cause_t wakeup_reason = esp_sleep_get_wakeup_cause();

  if (wakeup_reason == ESP_SLEEP_WAKEUP_TIMER) {
    // Timer expired - transition to deep sleep
    Serial.println("Light sleep timer expired, entering deep sleep...");
    Serial.flush();
    esp_deep_sleep_start();
  }

  // Woke from EXT1 (coil activity)
  Serial.println("Light sleep wakeup (coil activity)");
  stayAsleep = true;  // Keep re-entering sleep unless coil handler resets this
}
