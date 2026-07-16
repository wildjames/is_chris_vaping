# IsChrisVaping firmware build/upload targets
# Requires: GNU Make, PlatformIO CLI (pio)

NRF_DIR := firmware/nrf52840

.PHONY: help build upload

help:
	@echo "Usage: make <target>"
	@echo ""
	@echo "  build    Build NRF52840 firmware"
	@echo "  upload   Build and upload NRF52840 firmware"

# ── NRF52840 ─────────────────────────────────────────────────────────────────

build:
	cd $(NRF_DIR) && pio run -e nrf52840

upload:
	cd $(NRF_DIR) && pio run -e nrf52840 -t upload
