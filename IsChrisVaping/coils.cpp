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
static int coilACount = 0;
static int coilBCount = 0;

void coilsInit() {
  analogSetAttenuation(COIL_ATTENUATION);
  pinMode(COIL_A_PIN, INPUT);
  pinMode(COIL_B_PIN, INPUT);
}

void coilsUpdate() {
  // --- Coil A detection ---
  int coilAReading = analogRead(COIL_A_PIN);
  if (coilAReading > DRAW_THRESHOLD) {
    if (coilACount < DEBOUNCE_COUNT) coilACount++;
    if (coilACount >= DEBOUNCE_COUNT && !coilAActive) {
      coilAActive = true;
      lastActivityTime = millis();
      Serial.print("Coil A senses ");
      Serial.println(coilAReading);
      handleCoilAStarted();
    }
  } else {
    if (coilACount > 0) coilACount--;
    if (coilACount == 0 && coilAActive) {
      coilAActive = false;
      lastActivityTime = millis();
      handleCoilAStopped();
    }
  }

  // --- Coil B detection ---
  int coilBReading = analogRead(COIL_B_PIN);
  if (coilBReading > DRAW_THRESHOLD) {
    if (coilBCount < DEBOUNCE_COUNT) coilBCount++;
    if (coilBCount >= DEBOUNCE_COUNT && !coilBActive) {
      coilBActive = true;
      lastActivityTime = millis();
      Serial.print("Coil B senses ");
      Serial.println(coilBReading);
      handleCoilBStarted();
    }
  } else {
    if (coilBCount > 0) coilBCount--;
    if (coilBCount == 0 && coilBActive) {
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
