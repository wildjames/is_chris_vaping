# IsChrisVaping Firmware

Two firmware targets share this directory:

| Target | Board | Directory |
|--------|-------|-----------|
| **nRF52840** *(primary)* | Seeed XIAO nRF52840 | `nrf52840/` |
| **ESP32** *(legacy, has display)* | Custom ESP32 board | `esp32/` |

---

## nRF52840 (primary)

Seeed XIAO nRF52840 using PlatformIO + Arduino framework (Seeed nRF52 Boards / Adafruit-derived). No display; optimised for battery life.

### Power states

| State | Trigger | Avg. current | BLE |
|-------|---------|-------------|-----|
| Active | coil firing or recently active | ~50–200 µA | connected |
| Light sleep | 60 s idle | ~10–50 µA | **connected** (FreeRTOS blocks loop; SoftDevice runs) |
| System OFF | 30 min idle | ~1–5 µA | lost — re-advertises after reset |

Timeouts are `LIGHT_SLEEP_TIMEOUT_MS` and `DEEP_SLEEP_TIMEOUT_MS` in `nrf52840/src/sleep.h`.

### Prerequisites

- **PlatformIO Core** (any supported Python version — no ESP-IDF quirks)

```powershell
pip install platformio
```

### Building

```powershell
cd firmware/nrf52840
pio run -e nrf52840
```

### Flashing

Connect the XIAO via USB-C. Double-tap the reset button if it doesn't appear as a serial port.

```powershell
cd firmware/nrf52840
pio run -e nrf52840 -t upload
```

To find the port:

```powershell
pio device list
```

### Serial monitor

```powershell
pio device monitor --baud 115200
```

### OTA (firmware update over BLE)

The firmware exposes a Nordic DFU service. Flash updates wirelessly using the **nRF Connect** app (iOS/Android):

1. Build a new binary: `pio run -e nrf52840`
2. Copy `.pio/build/nrf52840/firmware.hex` to your phone
3. In nRF Connect → connect to *IsChrisVaping* → DFU → select the `.hex` file

### Configuration

Key constants:

| File | Constant | Default | Effect |
|------|----------|---------|--------|
| `src/sleep.h` | `LIGHT_SLEEP_TIMEOUT_MS` | 60 000 ms | Idle time before light sleep |
| `src/sleep.h` | `DEEP_SLEEP_TIMEOUT_MS` | 1 800 000 ms | Idle time before System OFF |
| `src/bluetooth.h` | `DEFAULT_VAPE_NAME` | `"My Vape"` | Name prefix for first-boot default |

### Troubleshooting

| Issue | Fix |
|-------|-----|
| Board not detected | Double-tap reset to enter UF2 bootloader mode |
| Build fails on first run | PlatformIO downloads the Seeed nRF52 core (~200 MB); allow time |
| BLE not advertising after System OFF wake | Expected — full reset occurs; advertising starts automatically |
| `xSemaphoreCreateBinary` linker error | Ensure `framework = arduino` in `platformio.ini` (not mbed) |

---

## ESP32 (legacy)

ESP32 firmware using PlatformIO with combined Arduino + ESP-IDF framework. This enables ESP-IDF sdkconfig control (power management, BLE modem sleep) while keeping Arduino libraries. Includes a display.

### Prerequisites

- **Python 3.12** (Python 3.13+ breaks ESP-IDF tooling)
- **PlatformIO Core** installed in the Python 3.12 environment

```powershell
conda create -n py312 python=3.12 -y
conda activate py312
pip install platformio
```

### Building

```powershell
cd firmware/esp32
conda activate py312
$env:IDF_COMPONENT_MANAGER = "0"
pio run -e esp32
```

> `IDF_COMPONENT_MANAGER=0` is required to work around a Python compatibility issue in `idf_component_manager`.

### Flashing

```powershell
$env:IDF_COMPONENT_MANAGER = "0"
pio run -e esp32 -t upload
```

For the 4MB dev kit (no external 32kHz crystal):

```powershell
$env:IDF_COMPONENT_MANAGER = "0"
pio run -e esp32_4mb -t upload
```

The board is configured to upload via COM10. Change `upload_port` in `platformio.ini` if your board is on a different port.

To see what COM port your board is on, run:

```powershell
pio device list
```

### Serial monitor

```powershell
pio device monitor --port COM10 --baud 115200
```

### Configuration

#### sdkconfig.esp32

This is the ESP-IDF configuration file that PlatformIO actually uses (it looks for `sdkconfig.<env_name>`). Key settings:

- **Bluetooth:** BLE-only mode with Bluedroid stack
- **Power Management:** `CONFIG_PM_ENABLE=y` with tickless idle for automatic light sleep
- **RTC Clock:** External 32.768kHz crystal (`CONFIG_ESP32_RTC_CLK_SRC_EXT_CRYS=y`)
- **BT Modem Sleep:** Maintains BLE connection during light sleep using the external crystal
- **Arduino:** `CONFIG_AUTOSTART_ARDUINO=y` enables `setup()`/`loop()` entry point

#### platformio.ini

- `framework = arduino, espidf` — combined mode, recompiles ESP-IDF from source
- `lib_extra_dirs` — points to the Arduino framework's built-in libraries (for BLE)
- `build_flags = -DCONFIG_AUTOSTART_ARDUINO=1` — ensures Arduino's `app_main()` wrapper is compiled

#### sdkconfig.defaults

Contains desired non-default settings. Note: PlatformIO doesn't reliably pass this to CMake's confgen in combined mode. If you need to change ESP-IDF settings, edit `sdkconfig.esp32` directly, or delete it and let it regenerate (then re-apply BT settings).

### Troubleshooting

| Issue | Fix |
|-------|-----|
| `idf_component_manager` crash | Set `$env:IDF_COMPONENT_MANAGER = "0"` |
| JSON parsing error in espidf.py | Use Python 3.12, not 3.13+ |
| BLE types not found (`BLEServer` etc.) | Ensure `CONFIG_BT_ENABLED=y` and `CONFIG_BT_BLUEDROID_ENABLED=y` in `sdkconfig.esp32` |
| `undefined reference to app_main` | Ensure `CONFIG_AUTOSTART_ARDUINO=y` in `sdkconfig.esp32` |
| Build uses stale config after changes | Delete `.pio/build/esp32/` and rebuild |
