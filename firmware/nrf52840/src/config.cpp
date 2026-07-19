#include "config.h"
#include <Adafruit_LittleFS.h>
#include <InternalFileSystem.h>

using namespace Adafruit_LittleFS_Namespace;

#define PIN_CONFIG_FILE "/pinconfig.bin"

// Stored pin configuration
static uint8_t coilAPin;
static uint8_t coilBPin;
static uint32_t coilANrfGpio;
static uint32_t coilBNrfGpio;

// Simple binary format: [version_byte, coilA_pin, coilB_pin]
#define PIN_CONFIG_VERSION 1
#define PIN_CONFIG_SIZE    3

static void writeDefaults() {
    coilAPin = DEFAULT_COIL_A_PIN;
    coilBPin = DEFAULT_COIL_B_PIN;

    InternalFS.remove(PIN_CONFIG_FILE);
    File wf(InternalFS);
    wf.open(PIN_CONFIG_FILE, FILE_O_WRITE);
    if (wf) {
        uint8_t buf[PIN_CONFIG_SIZE] = {
            PIN_CONFIG_VERSION, coilAPin, coilBPin
        };
        wf.write(buf, PIN_CONFIG_SIZE);
        wf.close();
    }
    Serial.printf("Config: wrote default pins to flash (A=%u, B=%u)\n",
                  coilAPin, coilBPin);
}

void configInit() {
    InternalFS.begin();

#ifdef FORCE_DEFAULT_CONFIG
    // USB flash: always overwrite with compiled defaults
    writeDefaults();
#else
    // OTA / normal boot: use stored config, write defaults only on first boot
    File f(InternalFS);
    f.open(PIN_CONFIG_FILE, FILE_O_READ);

    if (f && f.size() == PIN_CONFIG_SIZE) {
        uint8_t buf[PIN_CONFIG_SIZE];
        f.read(buf, PIN_CONFIG_SIZE);
        f.close();

        if (buf[0] == PIN_CONFIG_VERSION &&
            buf[1] < PINS_COUNT && buf[2] < PINS_COUNT) {
            coilAPin = buf[1];
            coilBPin = buf[2];
            Serial.printf("Config: loaded pins from flash (A=%u, B=%u)\n",
                          coilAPin, coilBPin);
        } else {
            Serial.println("Config: invalid or corrupt pin data, using defaults");
            writeDefaults();
        }
    } else {
        if (f) f.close();
        writeDefaults();
    }
#endif

    // Derive raw nRF GPIO numbers from Arduino pin numbers
    coilANrfGpio = g_ADigitalPinMap[coilAPin];
    coilBNrfGpio = g_ADigitalPinMap[coilBPin];

    Serial.printf("Config: nRF GPIO A=%lu, B=%lu\n", coilANrfGpio, coilBNrfGpio);
}

uint8_t getCoilAPin() { return coilAPin; }
uint8_t getCoilBPin() { return coilBPin; }
uint32_t getCoilANrfGpio() { return coilANrfGpio; }
uint32_t getCoilBNrfGpio() { return coilBNrfGpio; }
