#ifndef COILS_H
#define COILS_H

#include <Arduino.h>

// Coil sensing pins
#define COIL_A_PIN 12
#define COIL_B_PIN 14

// Voltage threshold for detecting a draw
// With 2:1 voltage divider: 4V coil -> 2V at pin, 1.2V check -> 0.6V at pin
// Threshold at ~1.2V (midpoint) = 1365 ADC counts (11dB attenuation, 0-3.6V range)
#define DRAW_THRESHOLD 1365

// Debounce: coil must be above threshold for this many consecutive reads
#define DEBOUNCE_COUNT 5

extern bool coilAActive;
extern bool coilBActive;

void coilsInit();
void coilsUpdate();
void handleCoilAStarted();
void handleCoilAStopped();
void handleCoilBStarted();
void handleCoilBStopped();

#endif
