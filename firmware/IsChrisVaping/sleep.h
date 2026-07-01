#ifndef SLEEP_H
#define SLEEP_H

#include <Arduino.h>

// Display turns off after this much inactivity (power saving)
// The system enters light sleep automatically via FreeRTOS tickless idle;
// BLE connection is maintained throughout by the BT modem sleep controller.
#define DISPLAY_OFF_TIMEOUT_MS  60000  // 60s inactivity -> display off

void sleepInit();
void sleepUpdate();

#endif
