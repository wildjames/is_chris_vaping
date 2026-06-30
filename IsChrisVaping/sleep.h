#ifndef SLEEP_H
#define SLEEP_H

#include <Arduino.h>

// Sleep timing
#define LIGHT_SLEEP_TIMEOUT_MS  60000      // 60s inactivity -> light sleep

void sleepUpdate();

#endif
