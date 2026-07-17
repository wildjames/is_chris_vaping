#pragma once

#include <Arduino.h>

// After LIGHT_SLEEP_TIMEOUT_MS of coil inactivity the CPU enters light sleep:
// the FreeRTOS loop task blocks, the SoftDevice continues running, and the BLE
// connection is maintained.  The device wakes immediately when either coil pin
// goes HIGH (GPIO interrupt → binary semaphore → task unblocks).
#define LIGHT_SLEEP_TIMEOUT_MS   (10UL * 1000UL)

// After DEEP_SLEEP_TIMEOUT_MS of coil inactivity the device enters System OFF:
// the chip fully powers down (<5 µA) and hard-resets on wake.  BLE is lost and
// re-advertises from scratch after the reset.
#define DEEP_SLEEP_TIMEOUT_MS    (1UL * 60UL * 1000UL)

void sleepInit();
void sleepUpdate();
