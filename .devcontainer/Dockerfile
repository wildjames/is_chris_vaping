FROM mcr.microsoft.com/devcontainers/python:3.12

# Switch to root for installing system-wide tools
USER root

# Install arduino-cli
RUN curl -fsSL https://raw.githubusercontent.com/arduino/arduino-cli/master/install.sh | BINDIR=/usr/local/bin sh

USER vscode
ENV PATH="/home/vscode/.local/bin:${PATH}"
