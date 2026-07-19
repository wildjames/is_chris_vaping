#pragma once

#include <Arduino.h>

// Default pin assignments — used on first boot only, then stored in flash.
// Change these before the initial upload if your hardware wiring differs.
#define DEFAULT_COIL_A_PIN  D10
#define DEFAULT_COIL_B_PIN  D1

// Initialise pin configuration from flash (or write defaults on first boot).
// Must be called before coilsInit() and sleepInit().
void configInit();

// Runtime accessors for the configured pins
uint8_t getCoilAPin();
uint8_t getCoilBPin();

// Raw nRF GPIO numbers (derived from Arduino pin at load time)
uint32_t getCoilANrfGpio();
uint32_t getCoilBNrfGpio();
