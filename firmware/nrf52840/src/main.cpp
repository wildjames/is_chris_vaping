#include <Arduino.h>
#include "version.h"
#include "config.h"
#include "bluetooth.h"
#include "coils.h"
#include "sleep.h"

// Shared state — also referenced by coils.cpp and sleep.cpp
unsigned long lastActivityTime    = 0;
unsigned long notRippedTimerStart = 0;
bool          notRippedTimerActive = false;

// Delay before sending NOT_RIPPED after a coil stops
static const unsigned long NOT_RIPPED_DELAY_MS = 3000;

void setup() {
    Serial.begin(115200);

    configInit();
    bluetoothInit();
    coilsInit();
    sleepInit();

    lastActivityTime = millis();
    Serial.printf("WhoIsVaping nRF52 firmware %s ready\n", FIRMWARE_VERSION);
}

void loop() {
    coilsUpdate();

    // Send NOT_RIPPED notification after a short delay once both coils are idle
    if (notRippedTimerActive &&
        (millis() - notRippedTimerStart >= NOT_RIPPED_DELAY_MS)) {
        notRippedTimerActive = false;
        sendBLEMessage(MSG_NOT_RIPPED);
    }

    // Enter light sleep or System OFF depending on how long the device has
    // been idle.  See sleep.h for the timeout constants.
    // - Light sleep (>60 s): loop task blocks on a semaphore; SoftDevice keeps
    //   BLE alive; coil GPIO interrupt unblocks the task immediately.
    // - System OFF  (>30 min): full chip reset on wake; BLE re-advertises.
    sleepUpdate();

    // While awake, yield to the SoftDevice scheduler.  The Adafruit nRF52 core
    // calls sd_app_evt_wait() from the FreeRTOS idle task, so the CPU sleeps
    // between BLE connection events without any extra configuration.
    delay(10);
}
