#ifndef SLEEP_H
#define SLEEP_H

#include <Arduino.h>

// Sleep timing
#define LIGHT_SLEEP_TIMEOUT_MS  60000      // 60s inactivity -> light sleep
#define DEEP_SLEEP_TIMEOUT_MS   3600000    // 1 hour in light sleep -> deep sleep

void sleepCheckWakeup();
void sleepUpdate();

#endif
