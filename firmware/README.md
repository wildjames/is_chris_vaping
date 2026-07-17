# IsChrisVaping Firmware

Seeed XIAO nRF52840 firmware using PlatformIO + Arduino framework (Seeed nRF52 Boards / Adafruit-derived).

## Power states

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
