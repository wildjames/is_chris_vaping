#include "coils.h"
#include "display.h"
#include "bluetooth.h"

// Shared state
extern unsigned long lastActivityTime;
extern bool notRippedTimerActive;
extern unsigned long notRippedTimerStart;

// Debounce: require 100ms of continuous LOW before counting as stopped
#define COIL_DEBOUNCE_MS 100

struct CoilState {
  uint8_t pin;
  bool active;
  bool lowTiming;
  unsigned long lowStart;
  void (*onStarted)();
  void (*onStopped)();
  const char *name;
};

static CoilState coils[] = {
  {COIL_A_PIN, false, false, 0, handleCoilAStarted, handleCoilAStopped, "Coil A"},
  {COIL_B_PIN, false, false, 0, handleCoilBStarted, handleCoilBStopped, "Coil B"},
};

bool coilAActive = false;
bool coilBActive = false;

void coilsInit() {
  for (auto &c : coils) pinMode(c.pin, INPUT);
}

void coilsUpdate() {
  for (auto &c : coils) {
    // If the coil goes HIGH for a single read, consider the coil active immediately.
    // However, if the coil goes LOW, require it to stay LOW for COIL_DEBOUNCE_MS before considering it inactive.

    if (digitalRead(c.pin) == HIGH) {
      c.lowTiming = false;
      // Rising edge detection
      if (!c.active) {
        c.active = true;
        lastActivityTime = millis();
        Serial.println(String(c.name) + " active");
        c.onStarted();
      }

    } else if (c.active) {
      // Coil is currently active but pin is LOW, start debounce timer
      if (!c.lowTiming) {
        c.lowTiming = true;
        c.lowStart = millis();
      } else if (millis() - c.lowStart >= COIL_DEBOUNCE_MS) {
        // Coil has been LOW for COIL_DEBOUNCE_MS, consider it stopped
        Serial.println(String(c.name) + " inactive");
        c.active = false;
        c.lowTiming = false;
        lastActivityTime = millis();
        c.onStopped();
      }
    }
  }

  // Then update the state flags
  coilAActive = coils[0].active;
  coilBActive = coils[1].active;
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
  showText("QUIT\nRIPPIN'\nA");
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
  showText("QUIT\nRIPPIN'\nB");
  notRippedTimerStart = millis();
  notRippedTimerActive = true;
}
