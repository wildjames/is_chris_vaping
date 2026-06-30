#ifndef COILS_H
#define COILS_H

#include <Arduino.h>

// Coil sensing pins
#define COIL_A_PIN 12
#define COIL_B_PIN 14

extern bool coilAActive;
extern bool coilBActive;

void coilsInit();
void coilsUpdate();
void handleCoilAStarted();
void handleCoilAStopped();
void handleCoilBStarted();
void handleCoilBStopped();

#endif
