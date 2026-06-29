#!/usr/bin/env python3
"""Upload compiled firmware to the vape server for OTA updates."""

import argparse
import sys

import requests


def main():
    parser = argparse.ArgumentParser(description="Upload firmware to OTA server")
    parser.add_argument("firmware", help="Path to the .bin firmware file")
    parser.add_argument("version", help="Firmware version (e.g. 1.1.0)")
    parser.add_argument("--server", required=True, help="Server base URL (e.g. https://example.com)")
    parser.add_argument("--token", required=True, help="API auth token")
    args = parser.parse_args()

    with open(args.firmware, "rb") as f:
        files = {"file": (args.firmware, f, "application/octet-stream")}
        response = requests.post(
            f"{args.server.rstrip('/')}/firmware/upload",
            params={"version": args.version},
            headers={"Authorization": f"Bearer {args.token}"},
            files=files,
        )

    if response.status_code == 200:
        data = response.json()
        print(f"Upload successful: v{data['version']} ({data['size']} bytes)")
    else:
        print(f"Upload failed ({response.status_code}): {response.text}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
