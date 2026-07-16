# IsChrisVaping firmware build/upload targets
# Requires: GNU Make, PlatformIO CLI (pio), adafruit-nrfutil

NRF_DIR := firmware/nrf52840
HEX_FILE := $(NRF_DIR)/.pio/build/nrf52840/firmware.hex
DFU_ZIP := dfu-package.zip

.PHONY: help build upload dfu-package

help:
	@echo "Usage: make <target>"
	@echo ""
	@echo "  build        Build NRF52840 firmware"
	@echo "  upload       Build and upload NRF52840 firmware via USB"
	@echo "  dfu-package  Build firmware and create DFU ZIP for OTA update"

# ── NRF52840 ─────────────────────────────────────────────────────────────────

build:
	cd $(NRF_DIR) && pio run -e nrf52840

upload:
	cd $(NRF_DIR) && pio run -e nrf52840 -t upload

dfu-package: build
	adafruit-nrfutil dfu genpkg --dev-type 0x0052 --sd-req 0xFFFE --application $(HEX_FILE) $(DFU_ZIP)
	@echo "DFU package created: $(DFU_ZIP)"
