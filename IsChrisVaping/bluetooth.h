#ifndef BLUETOOTH_H
#define BLUETOOTH_H

#include "version.h"
#include <BLEDevice.h>
#include <BLEServer.h>
#include <BLEUtils.h>
#include <BLE2902.h>

// UUIDs for BLE service and characteristic
#define SERVICE_UUID        "189a9192-f68f-4ac4-962e-d70e7c3755a0"
#define CHARACTERISTIC_UUID "5cf4a205-84e1-42ad-ac23-e5adc776a992"

extern BLEServer* pServer;
extern BLECharacteristic* pCharacteristic;
extern bool deviceConnected;
extern bool previousConnected;

// BLE message definitions
extern const char* MSG_COIL_A_STARTED;
extern const char* MSG_COIL_A_STOPPED;
extern const char* MSG_COIL_B_STARTED;
extern const char* MSG_COIL_B_STOPPED;

void bluetoothInit();
void sendBLEMessage(const char* msg);

#endif
