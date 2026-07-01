#include "sleep.h"
#include "display.h"
#include "coils.h"
#include "bluetooth.h"
#include "ota.h"
#include <esp_pm.h>
#include <esp_sleep.h>

// Shared state
extern unsigned long lastActivityTime;

static bool displayOff = false;

void sleepInit() {
  // Configure power management for automatic light sleep.
  // With BT modem sleep using the external 32K crystal, the BLE connection
  // is maintained: the BT controller wakes the system for connection events
  // and sleeps in between.
  esp_pm_config_esp32_t pm_config = {
    .max_freq_mhz = 80,
    .min_freq_mhz = 10,
    .light_sleep_enable = true
  };
  esp_err_t err = esp_pm_configure(&pm_config);
  if (err != ESP_OK) {
    Serial.printf("PM configure failed: %s\n", esp_err_to_name(err));
    return;
  }
  Serial.println("Automatic light sleep enabled (BLE stays connected)");

  // Configure ext1 wakeup so coil activity wakes from light sleep immediately
  uint64_t wakeup_mask = (1ULL << COIL_A_PIN) | (1ULL << COIL_B_PIN);
  esp_sleep_enable_ext1_wakeup(wakeup_mask, ESP_EXT1_WAKEUP_ANY_HIGH);
  Serial.println("EXT1 wakeup configured for coil pins");
}

void sleepUpdate() {
  if (otaInProgress || coilAActive || coilBActive) {
    if (displayOff) {
      tft.writeCommand(ST77XX_DISPON);
      analogWrite(LCD_BLK, LCD_BRIGHTNESS);
      displayOff = false;
    }
    return;
  }

  if (millis() - lastActivityTime > DISPLAY_OFF_TIMEOUT_MS) {
    if (!displayOff) {
      analogWrite(LCD_BLK, 0);
      tft.writeCommand(ST77XX_DISPOFF);
      displayOff = true;
      Serial.println("Display off (auto light sleep active)");
    }
  } else {
    if (displayOff) {
      tft.writeCommand(ST77XX_DISPON);
      analogWrite(LCD_BLK, LCD_BRIGHTNESS);
      displayOff = false;
    }
  }
}
