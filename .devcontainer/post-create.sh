#!/bin/bash
set -e

# Install Python dev dependencies
pip install -r requirements-dev.txt

# Configure arduino-cli and install ESP32 core
arduino-cli config init --overwrite
arduino-cli config add board_manager.additional_urls https://raw.githubusercontent.com/espressif/arduino-esp32/gh-pages/package_esp32_index.json
arduino-cli core update-index
arduino-cli core install esp32:esp32@3.3.10
