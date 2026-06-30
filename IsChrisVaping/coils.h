#ifndef COILS_H
#define COILS_H

#include <Arduino.h>

// Coil sensing pins
#define COIL_A_PIN 12
#define COIL_B_PIN 14

// Voltage threshold for detecting a draw
// I measure the coil voltage at ~1V when active, and 0 when not.
// With 6dB attenuation (0-2.2V range), active signal reads ~1800 counts.
// Threshold set at ~900 (midpoint between noise floor and active signal).
#define COIL_ATTENUATION ADC_6db
#define DRAW_THRESHOLD 900

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
