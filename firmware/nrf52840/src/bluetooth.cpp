#include "bluetooth.h"
#include "ota.h"
#include "version.h"
#include <Adafruit_LittleFS.h>
#include <InternalFileSystem.h>

using namespace Adafruit_LittleFS_Namespace;

// BLE objects
BLEService        vapeSvc(SERVICE_UUID);
BLECharacteristic coilChar(CHARACTERISTIC_UUID);
BLECharacteristic nameChar(NAME_CHARACTERISTIC_UUID);

// OTA DFU service - Nordic DFU protocol; update via nRF Connect or similar
static BLEDfu bledfu;

// Shared state
char vapeName[MAX_VAPE_NAME_LEN + 1] = DEFAULT_VAPE_NAME;
bool deviceConnected = false;

const char* MSG_COIL_A_STARTED = "COIL_A:STARTED";
const char* MSG_COIL_A_STOPPED = "COIL_A:STOPPED";
const char* MSG_COIL_B_STARTED = "COIL_B:STARTED";
const char* MSG_COIL_B_STOPPED = "COIL_B:STOPPED";
const char* MSG_NOT_RIPPED     = "NOT_RIPPED";

#define VAPE_NAME_FILE "/vapename.txt"

// ---------------------------------------------------------------------------
// Persistent storage
// ---------------------------------------------------------------------------

void loadVapeName() {
    InternalFS.begin();

    File f(InternalFS);
    f.open(VAPE_NAME_FILE, FILE_O_READ);
    if (f) {
        size_t len = f.read((uint8_t*)vapeName, MAX_VAPE_NAME_LEN);
        vapeName[len] = '\0';
        f.close();
        Serial.printf("Loaded vape name: %s\n", vapeName);
    } else {
        // First boot: generate a unique default name
        char defaultName[MAX_VAPE_NAME_LEN + 1];
        snprintf(defaultName, sizeof(defaultName), "%s %04d",
                 DEFAULT_VAPE_NAME, (int)random(0, 10000));
        saveVapeName(defaultName);
        Serial.printf("Generated vape name: %s\n", vapeName);
    }
}

void saveVapeName(const char* name) {
    strncpy(vapeName, name, MAX_VAPE_NAME_LEN);
    vapeName[MAX_VAPE_NAME_LEN] = '\0';

    InternalFS.begin();
    InternalFS.remove(VAPE_NAME_FILE);

    File f(InternalFS);
    f.open(VAPE_NAME_FILE, FILE_O_WRITE);
    if (f) {
        f.write((const uint8_t*)vapeName, strlen(vapeName));
        f.close();
    }
    Serial.printf("Saved vape name: %s\n", vapeName);
}

// ---------------------------------------------------------------------------
// BLE callbacks
// ---------------------------------------------------------------------------

static void connectCallback(uint16_t conn_hdl) {
    (void)conn_hdl;
    deviceConnected = true;
    digitalWrite(LED_RED, LOW);  // Active-low: LOW = on
    Serial.println("BLE connected");
    // Stop advertising while connected to save power
    Bluefruit.Advertising.stop();
}

static void disconnectCallback(uint16_t conn_hdl, uint8_t reason) {
    (void)conn_hdl;
    deviceConnected = false;
    digitalWrite(LED_RED, HIGH);  // Active-low: HIGH = off
    Serial.printf("BLE disconnected (reason=0x%02X)\n", reason);
    // Resume advertising so the phone can reconnect
    Bluefruit.Advertising.start(0);
}

static void pairCompleteCallback(uint16_t conn_hdl, uint8_t auth_status) {
    BLEConnection* conn = Bluefruit.Connection(conn_hdl);
    if (auth_status == BLE_GAP_SEC_STATUS_SUCCESS) {
        Serial.printf("Paired successfully, bonded=%d\n", conn->bonded());
    } else {
        Serial.printf("Pairing failed, status=0x%02X\n", auth_status);
    }
}

static void securedCallback(uint16_t conn_hdl) {
    Serial.printf("Connection secured (encrypted), conn_hdl=%d\n", conn_hdl);
}

// ---------------------------------------------------------------------------
// BLE advertised name
// ---------------------------------------------------------------------------

// BLE GAP device names can be up to 248 bytes, but the scan response
// payload that carries the complete local name is at most 31 bytes
// (29 usable after the AD type/length header).  We build
// "<vapeName>'s Vape" and truncate if necessary.
#define BLE_ADV_NAME_MAX 29
static char bleAdvName[BLE_ADV_NAME_MAX + 1];

static void updateBleName() {
    snprintf(bleAdvName, sizeof(bleAdvName), "%s's Vape", vapeName);
    Bluefruit.setName(bleAdvName);
}

static void nameWriteCallback(uint16_t conn_hdl, BLECharacteristic* chr,
                               uint8_t* data, uint16_t len) {
    (void)conn_hdl;
    (void)chr;
    if (len == 0 || len > MAX_VAPE_NAME_LEN) return;

    char name[MAX_VAPE_NAME_LEN + 1];
    memcpy(name, data, len);
    name[len] = '\0';

    saveVapeName(name);
    // Reflect the new name back to the characteristic
    nameChar.write(vapeName, strlen(vapeName));
    // Update the BLE advertised name and restart advertising so scanners
    // pick up the change after the current connection drops.
    updateBleName();
    Serial.printf("Name updated via BLE: %s\n", vapeName);
}


// ---------------------------------------------------------------------------
// Public API
// ---------------------------------------------------------------------------

void sendBLEMessage(const char* msg) {
    if (!deviceConnected) {
        Serial.printf("BLE not connected, dropping: %s\n", msg);
        return;
    }
    coilChar.notify((uint8_t*)msg, strlen(msg));
    Serial.printf("Sent: %s\n", msg);
}

void bluetoothInit() {
    loadVapeName();

    // Red LED indicates BLE connection status
    pinMode(LED_RED, OUTPUT);
    digitalWrite(LED_RED, HIGH);  // Start off (active-low)

    Bluefruit.begin();
    updateBleName();
    // TX power +4 dBm - decent range while staying within BLE spec
    Bluefruit.setTxPower(4);

    // --- BLE Security: enable bonding with "Just Works" pairing ---
    // This is required for Nordic DFU to work reliably. Without bonding, the
    // bootloader can't reconnect to phones that use random resolvable addresses
    // (which is all modern Android/iOS devices). Bonding shares the IRK so the
    // bootloader can resolve the phone's address after reboot.
    Bluefruit.Security.setIOCaps(false, false, false);  // No display, no yes/no, no keyboard
    Bluefruit.Security.setMITM(false);                  // Just Works (no MITM protection)
    Bluefruit.Security.setPairCompleteCallback(pairCompleteCallback);
    Bluefruit.Security.setSecuredCallback(securedCallback);

    Bluefruit.Periph.setConnectCallback(connectCallback);
    Bluefruit.Periph.setDisconnectCallback(disconnectCallback);

    // Request a long connection interval to minimise radio wake-ups.
    // Values are in units of 1.25 ms: 800 = 1 s, 1600 = 2 s.
    // The central (phone) is free to negotiate a shorter interval; this is
    // only a preference, not a hard requirement.
    Bluefruit.Periph.setConnInterval(800, 1600);

    // DFU service must be set up before starting the peripheral service
    bledfu.begin();

    // Main vape service
    vapeSvc.begin();

    // Coil activity characteristic (notify + read) - requires encrypted link
    // so the phone must pair/bond before it can subscribe to notifications.
    coilChar.setProperties(CHR_PROPS_READ | CHR_PROPS_NOTIFY);
    coilChar.setPermission(SECMODE_ENC_NO_MITM, SECMODE_NO_ACCESS);
    coilChar.setMaxLen(64);
    coilChar.begin();
    coilChar.write("READY", 5);

    // Device name characteristic (read + write) - requires encrypted link
    nameChar.setProperties(CHR_PROPS_READ | CHR_PROPS_WRITE);
    nameChar.setPermission(SECMODE_ENC_NO_MITM, SECMODE_ENC_NO_MITM);
    nameChar.setMaxLen(MAX_VAPE_NAME_LEN);
    nameChar.setWriteCallback(nameWriteCallback);
    nameChar.begin();
    nameChar.write(vapeName, strlen(vapeName));

    // OTA service - must be set up before advertising starts
    otaInit();

    // Advertising - fast for 30 s then slow (saves power during long idle)
    Bluefruit.Advertising.addFlags(BLE_GAP_ADV_FLAGS_LE_ONLY_GENERAL_DISC_MODE);
    Bluefruit.Advertising.addTxPower();
    Bluefruit.Advertising.addService(vapeSvc);
    Bluefruit.ScanResponse.addName();
    Bluefruit.Advertising.restartOnDisconnect(true);
    Bluefruit.Advertising.setInterval(160, 1600);  // 100 ms fast / 1 s slow
    Bluefruit.Advertising.setFastTimeout(30);
    Bluefruit.Advertising.start(0);  // advertise until connected

    Serial.printf("BLE ready. Device: %s, Name: %s, FW: %s\n",
                  bleAdvName, vapeName, FIRMWARE_VERSION);
}
