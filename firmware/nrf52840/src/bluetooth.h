#pragma once

#include <bluefruit.h>

// UUIDs — must match the companion app
#define SERVICE_UUID              "189a9192-f68f-4ac4-962e-d70e7c3755a0"
#define CHARACTERISTIC_UUID       "5cf4a205-84e1-42ad-ac23-e5adc776a992"
#define NAME_CHARACTERISTIC_UUID  "5cf4a205-84e1-42ad-ac23-e5adc776a993"

#define DEFAULT_VAPE_NAME  "My Vape"
#define MAX_VAPE_NAME_LEN  32

extern BLEService        vapeSvc;
extern BLECharacteristic coilChar;
extern BLECharacteristic nameChar;

extern char vapeName[MAX_VAPE_NAME_LEN + 1];
extern bool deviceConnected;

extern const char* MSG_COIL_A_STARTED;
extern const char* MSG_COIL_A_STOPPED;
extern const char* MSG_COIL_B_STARTED;
extern const char* MSG_COIL_B_STOPPED;
extern const char* MSG_NOT_RIPPED;

void bluetoothInit();
void sendBLEMessage(const char* msg);
void loadVapeName();
void saveVapeName(const char* name);
