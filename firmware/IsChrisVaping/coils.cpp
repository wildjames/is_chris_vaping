#include "coils.h"
#include "display.h"
#include "bluetooth.h"

// Shared state
extern unsigned long lastActivityTime;
extern bool notRippedTimerActive;
extern unsigned long notRippedTimerStart;

// Coil state tracking
bool coilAActive = false;
bool coilBActive = false;

void coilsInit() {
  pinMode(COIL_A_PIN, INPUT);
  pinMode(COIL_B_PIN, INPUT);
}

void coilsUpdate() {
  // --- Coil A detection ---
  if (digitalRead(COIL_A_PIN) == HIGH) {
    if (!coilAActive) {
      coilAActive = true;
      lastActivityTime = millis();
      Serial.println("Coil A active");
      handleCoilAStarted();
    }
  } else {
    if (coilAActive) {
      coilAActive = false;
      lastActivityTime = millis();
      handleCoilAStopped();
    }
  }

  // --- Coil B detection ---
  if (digitalRead(COIL_B_PIN) == HIGH) {
    if (!coilBActive) {
      coilBActive = true;
      lastActivityTime = millis();
      Serial.println("Coil B active");
      handleCoilBStarted();
    }
  } else {
    if (coilBActive) {
      coilBActive = false;
      lastActivityTime = millis();
      handleCoilBStopped();
    }
  }
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
