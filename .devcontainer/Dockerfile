FROM mcr.microsoft.com/devcontainers/python:3.12

# Switch to root for installing system-wide tools
USER root

# Install arduino-cli
RUN curl -fsSL https://raw.githubusercontent.com/arduino/arduino-cli/master/install.sh | BINDIR=/usr/local/bin sh

# Install ESP32 core
RUN arduino-cli config init && \
arduino-cli config add board_manager.additional_urls https://raw.githubusercontent.com/espressif/arduino-esp32/gh-pages/package_esp32_index.json && \
arduino-cli core update-index && \
arduino-cli core install esp32:esp32@3.3.10

# Install Python dependencies for the server and helper scripts
COPY requirements-dev.txt /tmp/requirements-dev.txt
RUN pip install --no-cache-dir -r /tmp/requirements-dev.txt && rm /tmp/requirements-dev.txt

USER vscode
ENV PATH="/home/vscode/.local/bin:${PATH}"
