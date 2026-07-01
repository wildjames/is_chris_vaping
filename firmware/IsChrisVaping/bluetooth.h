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
#define NAME_CHARACTERISTIC_UUID "5cf4a205-84e1-42ad-ac23-e5adc776a993"

// Default device name
#define DEFAULT_VAPE_NAME "My Vape"
#define MAX_VAPE_NAME_LEN 32

extern BLEServer* pServer;
extern BLECharacteristic* pCharacteristic;
extern BLECharacteristic* pNameCharacteristic;
extern bool deviceConnected;
extern bool previousConnected;

// Device name stored in flash
extern char vapeName[MAX_VAPE_NAME_LEN + 1];
extern bool nameChanged;

// BLE message definitions
extern const char* MSG_COIL_A_STARTED;
extern const char* MSG_COIL_A_STOPPED;
extern const char* MSG_COIL_B_STARTED;
extern const char* MSG_COIL_B_STOPPED;

// Message buffer for offline events
#define MSG_BUFFER_SIZE 16
#define MSG_MAX_LEN 20
#define FLUSH_DELAY_MS 500  // Delay after connect to allow client to subscribe

extern bool pendingFlush;
extern unsigned long flushAfterMs;

void bluetoothInit();
void sendBLEMessage(const char* msg);
void flushBLEBuffer();
void bluetoothUpdate();
void loadVapeName();
void saveVapeName(const char* name);

#endif
