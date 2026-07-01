# IsChrisVaping Firmware

ESP32 firmware using PlatformIO with combined Arduino + ESP-IDF framework. This enables ESP-IDF sdkconfig control (power management, BLE modem sleep) while keeping Arduino libraries.

## Prerequisites

- **Python 3.12** (Python 3.13+ breaks ESP-IDF tooling)
- **PlatformIO Core** installed in the Python 3.12 environment

### Setup (one-time)

```powershell
conda create -n py312 python=3.12 -y
conda activate py312
pip install platformio
```

## Building

```powershell
cd firmware
conda activate py312
$env:IDF_COMPONENT_MANAGER = "0"
pio run -e esp32
```

> `IDF_COMPONENT_MANAGER=0` is required to work around a Python compatibility issue in `idf_component_manager`.

## Flashing

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

## Serial Monitor

```powershell
pio device monitor --port COM10 --baud 115200
```

## Configuration

### sdkconfig.esp32

This is the ESP-IDF configuration file that PlatformIO actually uses (it looks for `sdkconfig.<env_name>`). Key settings:

- **Bluetooth:** BLE-only mode with Bluedroid stack
- **Power Management:** `CONFIG_PM_ENABLE=y` with tickless idle for automatic light sleep
- **RTC Clock:** External 32.768kHz crystal (`CONFIG_ESP32_RTC_CLK_SRC_EXT_CRYS=y`)
- **BT Modem Sleep:** Maintains BLE connection during light sleep using the external crystal
- **Arduino:** `CONFIG_AUTOSTART_ARDUINO=y` enables `setup()`/`loop()` entry point

### platformio.ini

- `framework = arduino, espidf` — combined mode, recompiles ESP-IDF from source
- `lib_extra_dirs` — points to the Arduino framework's built-in libraries (for BLE)
- `build_flags = -DCONFIG_AUTOSTART_ARDUINO=1` — ensures Arduino's `app_main()` wrapper is compiled

### sdkconfig.defaults

Contains desired non-default settings. Note: PlatformIO doesn't reliably pass this to CMake's confgen in combined mode. If you need to change ESP-IDF settings, edit `sdkconfig.esp32` directly, or delete it and let it regenerate (then re-apply BT settings).

## Troubleshooting

| Issue | Fix |
|-------|-----|
| `idf_component_manager` crash | Set `$env:IDF_COMPONENT_MANAGER = "0"` |
| JSON parsing error in espidf.py | Use Python 3.12, not 3.13+ |
| BLE types not found (`BLEServer` etc.) | Ensure `CONFIG_BT_ENABLED=y` and `CONFIG_BT_BLUEDROID_ENABLED=y` in `sdkconfig.esp32` |
| `undefined reference to app_main` | Ensure `CONFIG_AUTOSTART_ARDUINO=y` in `sdkconfig.esp32` |
| Build uses stale config after changes | Delete `.pio/build/esp32/` and rebuild |
