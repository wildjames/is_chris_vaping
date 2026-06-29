#ifndef SLEEP_H
#define SLEEP_H

#include <Arduino.h>

// Sleep timing
#define LIGHT_SLEEP_TIMEOUT_MS  60000      // 60s inactivity -> light sleep
#define DEEP_SLEEP_TIMEOUT_MS  120000      // 2 min in light sleep -> deep sleep

void sleepCheckWakeup();
void sleepUpdate();

#endif
