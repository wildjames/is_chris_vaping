# IsChrisVaping firmware build/upload targets
# Requires: GNU Make, PlatformIO CLI (pio), conda (env py312 for ESP32 builds)
#
# ESP32 builds use Python 3.12 via conda to avoid ESP-IDF tooling breakage on
# Python 3.13+. IDF_COMPONENT_MANAGER=0 prevents a Python compat crash in
# idf_component_manager.

ESP32_DIR := firmware/esp32
NRF_DIR   := firmware/nrf52840

# Propagate to all child processes (required for ESP-IDF builds)
export IDF_COMPONENT_MANAGER := 0

.PHONY: help \
        build-esp32 upload-esp32 \
        build-esp32-4mb upload-esp32-4mb \
        build-nrf52840 upload-nrf52840 \
        build-all

help:
	@echo "Usage: make <target>"
	@echo ""
	@echo "  build-esp32       Build ESP32 firmware (16 MB flash)"
	@echo "  upload-esp32      Build and upload ESP32 firmware (16 MB flash)"
	@echo "  build-esp32-4mb   Build ESP32 firmware (4 MB flash)"
	@echo "  upload-esp32-4mb  Build and upload ESP32 firmware (4 MB flash)"
	@echo "  build-nrf52840    Build NRF52840 firmware"
	@echo "  upload-nrf52840   Build and upload NRF52840 firmware"
	@echo "  build-all         Build all three firmware variants"

# ── ESP32 (16 MB) ────────────────────────────────────────────────────────────

build-esp32:
	cd $(ESP32_DIR) && conda run -n py312 --no-capture-output pio run -e esp32

upload-esp32:
	cd $(ESP32_DIR) && conda run -n py312 --no-capture-output pio run -e esp32 -t upload

# ── ESP32 (4 MB) ─────────────────────────────────────────────────────────────

build-esp32-4mb:
	cd $(ESP32_DIR) && conda run -n py312 --no-capture-output pio run -e esp32_4mb

upload-esp32-4mb:
	cd $(ESP32_DIR) && conda run -n py312 --no-capture-output pio run -e esp32_4mb -t upload

# ── NRF52840 ─────────────────────────────────────────────────────────────────

build-nrf52840:
	cd $(NRF_DIR) && pio run -e nrf52840

upload-nrf52840:
	cd $(NRF_DIR) && pio run -e nrf52840 -t upload

# ── Aggregate ─────────────────────────────────────────────────────────────────

build-all: build-esp32 build-esp32-4mb build-nrf52840
