#include "sleep.h"
#include "config.h"
#include "coils.h"

#include <bluefruit.h>
#include <nrf_gpio.h>
#include <nrf_soc.h>
#include <Adafruit_SPIFlash.h>

// FreeRTOS ISR-safe semaphore API
#include <FreeRTOS.h>
#include <semphr.h>

extern unsigned long lastActivityTime;

// Binary semaphore: given by the coil ISR, taken by the blocked loop task.
// Created once in sleepInit() and reused across every light-sleep cycle.
static SemaphoreHandle_t coilWakeSem = NULL;

static Adafruit_FlashTransport_QSPI flashTransport;

// ---------------------------------------------------------------------------
// ISR — called on rising edge of either coil pin during light sleep
// ---------------------------------------------------------------------------

static void coilWakeISR() {
    BaseType_t xHigherPriorityTaskWoken = pdFALSE;
    xSemaphoreGiveFromISR(coilWakeSem, &xHigherPriorityTaskWoken);
    portYIELD_FROM_ISR(xHigherPriorityTaskWoken);
}

// ---------------------------------------------------------------------------
// Light sleep — BLE connection maintained, wakes immediately on coil activity
// ---------------------------------------------------------------------------

static void enterLightSleep() {
    Serial.println("Light sleep (BLE maintained) — waiting for coil activity");
    Serial.flush();

    digitalWrite(LED_RED, HIGH);  // Ensure LED off during sleep

    // Consume any stale token before blocking
    xSemaphoreTake(coilWakeSem, 0);

    attachInterrupt(digitalPinToInterrupt(getCoilAPin()), coilWakeISR, RISING);
    attachInterrupt(digitalPinToInterrupt(getCoilBPin()), coilWakeISR, RISING);

    // Block until coil activity OR until the deep sleep timeout is reached.
    // Without a bounded wait the loop would never advance to check the System
    // OFF condition, leaving the device in light sleep (blue LED flashing)
    // indefinitely.
    const unsigned long idle = millis() - lastActivityTime;
    const unsigned long remainingMs = (idle >= DEEP_SLEEP_TIMEOUT_MS)
                                         ? 0UL
                                         : (DEEP_SLEEP_TIMEOUT_MS - idle);
    xSemaphoreTake(coilWakeSem, pdMS_TO_TICKS(remainingMs));

    detachInterrupt(digitalPinToInterrupt(getCoilAPin()));
    detachInterrupt(digitalPinToInterrupt(getCoilBPin()));

    Serial.println("Woke from light sleep");
    // coilsUpdate() on the very next loop() iteration detects the HIGH pin
    // and fires the coil-started event + BLE notify.
}

// ---------------------------------------------------------------------------
// System OFF — full power-down (<5 µA), hard reset on wake, BLE lost
// ---------------------------------------------------------------------------

static void powerDownFlash() {
    flashTransport.begin();
    flashTransport.runCommand(0xB9);  // JEDEC deep power-down
    delay(10);
}

static void enterSystemOff() {
    Serial.println("System OFF — will hard-reset on coil activity");
    Serial.flush();

    // Stop BLE advertising so the library releases the blue LED
    Bluefruit.Advertising.stop();
    digitalWrite(LED_RED, HIGH);
    digitalWrite(LED_GREEN, HIGH);
    digitalWrite(LED_BLUE, HIGH);

    powerDownFlash();

    // Configure coil pins as high-sense wakeup sources before powering down.
    // GPIO DETECT wakes System OFF with a full chip reset.
    nrf_gpio_cfg_sense_input(getCoilANrfGpio(), NRF_GPIO_PIN_PULLDOWN,
                             NRF_GPIO_PIN_SENSE_HIGH);
    nrf_gpio_cfg_sense_input(getCoilBNrfGpio(), NRF_GPIO_PIN_PULLDOWN,
                             NRF_GPIO_PIN_SENSE_HIGH);

    sd_power_system_off();   // never returns

    // Unreachable — belt-and-braces if SoftDevice is already disabled
    NRF_POWER->SYSTEMOFF = 1;
    __WFE();
}

// ---------------------------------------------------------------------------
// Public API
// ---------------------------------------------------------------------------

void sleepInit() {
    coilWakeSem = xSemaphoreCreateBinary();
    Serial.printf("Sleep: light sleep after %lu s, System OFF after %lu min\n",
                  LIGHT_SLEEP_TIMEOUT_MS / 1000UL,
                  DEEP_SLEEP_TIMEOUT_MS  / 60000UL);
}

void sleepUpdate() {
    // Never sleep while a coil is actively firing
    if (coilAActive || coilBActive) return;

    unsigned long idle = millis() - lastActivityTime;

    if (idle > DEEP_SLEEP_TIMEOUT_MS) {
        enterSystemOff();
    } else if (idle > LIGHT_SLEEP_TIMEOUT_MS) {
        enterLightSleep();
        // Returns here when coil activity wakes us; the next coilsUpdate()
        // call in loop() detects the HIGH pin and sends the BLE message.
    }
}
