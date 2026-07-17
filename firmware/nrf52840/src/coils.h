#pragma once

#include <Arduino.h>

// Coil sense pins — XIAO nRF52840: D0 = P0.02, D1 = P0.03
#define COIL_A_PIN  D0
#define COIL_B_PIN  D1

extern bool coilAActive;
extern bool coilBActive;

void coilsInit();
void coilsUpdate();
