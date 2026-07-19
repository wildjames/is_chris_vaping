-include .env
export

# IsChrisVaping firmware build/upload targets
# Requires: GNU Make, PlatformIO CLI (pio), adafruit-nrfutil

NRF_DIR := firmware/nrf52840
HEX_FILE := $(NRF_DIR)/.pio/build/nrf52840/firmware.hex
HEX_FILE_OTA := $(NRF_DIR)/.pio/build/nrf52840_ota/firmware.hex
DFU_ZIP := dfu-package.zip

# Pass VERSION=x.y.z to inject the firmware version into the build.
# Without it the firmware reports "<dev>".
VERSION ?=

ifdef VERSION
export PLATFORMIO_BUILD_FLAGS := -DFIRMWARE_VERSION=\"$(VERSION)\"
endif

.PHONY: help build upload dfu-package dummy-vape

help:
	@echo "Usage: make <target> [VERSION=x.y.z]"
	@echo ""
	@echo "  build            Build NRF52840 firmware"
	@echo "  upload           Build and upload NRF52840 firmware via USB"
	@echo "  dfu-package      Build firmware and create DFU ZIP for OTA update"
	@echo "  dummy-vape       Run the dummy vape script"
	@echo ""
	@echo "Options:"
	@echo "  VERSION=x.y.z    Firmware version baked into the binary (default: <dev>)"

# ── NRF52840 ─────────────────────────────────────────────────────────────────

build:
	cd $(NRF_DIR) && pio run -e nrf52840

upload:
	cd $(NRF_DIR) && pio run -e nrf52840 -t upload

dfu-package:
	cd $(NRF_DIR) && pio run -e nrf52840_ota
	adafruit-nrfutil dfu genpkg --dev-type 0x0052 --sd-req 0xFFFE --application $(HEX_FILE_OTA) $(DFU_ZIP)
	@echo "DFU package created: $(DFU_ZIP)"

# ── Dev helpers ───────────────────────────────────────────────────────────────

dummy-vape:
	VAPE_API_TOKEN=$(VAPE_API_TOKEN) python dummy_vape.py
