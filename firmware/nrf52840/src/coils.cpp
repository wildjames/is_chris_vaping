#include "coils.h"
#include "config.h"
#include "bluetooth.h"

// Shared globals owned by main.cpp
extern unsigned long lastActivityTime;
extern bool          notRippedTimerActive;
extern unsigned long notRippedTimerStart;

// Require pin to stay LOW for this long before declaring a coil stopped.
// Prevents spurious stop events from switch bounce.
static constexpr unsigned long COIL_DEBOUNCE_MS = 500;

struct CoilState {
    uint8_t pin;
    bool    active;
    bool    lowTiming;
    unsigned long lowStart;
    void (*onStarted)();
    void (*onStopped)();
    const char* name;
};

static void handleCoilAStarted();
static void handleCoilAStopped();
static void handleCoilBStarted();
static void handleCoilBStopped();

static CoilState coils[] = {
    { 0, false, false, 0, handleCoilAStarted, handleCoilAStopped, "Coil A" },
    { 0, false, false, 0, handleCoilBStarted, handleCoilBStopped, "Coil B" },
};

bool coilAActive = false;
bool coilBActive = false;

void coilsInit() {
    coils[0].pin = getCoilAPin();
    coils[1].pin = getCoilBPin();
    for (auto& c : coils) {
        pinMode(c.pin, INPUT);
    }
}

void coilsUpdate() {
    for (auto& c : coils) {
        if (digitalRead(c.pin) == HIGH) {
            c.lowTiming = false;
            if (!c.active) {
                c.active = true;
                lastActivityTime = millis();
                Serial.printf("%s active\n", c.name);
                c.onStarted();
            }
        } else if (c.active) {
            // Pin is LOW but coil was active — start/extend debounce timer
            if (!c.lowTiming) {
                c.lowTiming = true;
                c.lowStart  = millis();
            } else if (millis() - c.lowStart >= COIL_DEBOUNCE_MS) {
                Serial.printf("%s inactive\n", c.name);
                c.active    = false;
                c.lowTiming = false;
                lastActivityTime = millis();
                c.onStopped();
            }
        }
    }

    coilAActive = coils[0].active;
    coilBActive = coils[1].active;
}

// ---------------------------------------------------------------------------
// Event handlers — no display, BLE messages only
// ---------------------------------------------------------------------------

static void handleCoilAStarted() {
    notRippedTimerActive = false;
    coilAActive          = true;
    lastActivityTime     = millis();
    sendBLEMessage(MSG_COIL_A_STARTED);
}

static void handleCoilAStopped() {
    coilAActive      = false;
    lastActivityTime = millis();
    sendBLEMessage(MSG_COIL_A_STOPPED);
    notRippedTimerStart  = millis();
    notRippedTimerActive = true;
}

static void handleCoilBStarted() {
    notRippedTimerActive = false;
    coilBActive          = true;
    lastActivityTime     = millis();
    sendBLEMessage(MSG_COIL_B_STARTED);
}

static void handleCoilBStopped() {
    coilBActive      = false;
    lastActivityTime = millis();
    sendBLEMessage(MSG_COIL_B_STOPPED);
    notRippedTimerStart  = millis();
    notRippedTimerActive = true;
}
