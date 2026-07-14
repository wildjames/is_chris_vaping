#!/usr/bin/env python3
"""Dummy vape simulator — sends active/inactive payloads to the local dev server."""

import os
import sys

import requests

SERVER_URL = os.environ.get("VAPE_SERVER_URL", "http://localhost:5000")
API_TOKEN = os.environ.get("VAPE_API_TOKEN", "")
VAPE_NAME = os.environ.get("VAPE_NAME", "dummy-vape")

HEADERS = {
    "Content-Type": "application/json",
    "Authorization": f"Bearer {API_TOKEN}",
}


def send_update(coil: str, event: str):
    url = f"{SERVER_URL}/vape-update"
    payload = {"coil": coil, "event": event, "vape_name": VAPE_NAME}
    try:
        resp = requests.post(url, json=payload, headers=HEADERS, timeout=5)
        print(f"  -> {resp.status_code}: {resp.json()}")
    except requests.RequestException as e:
        print(f"  -> Error: {e}")


def main():
    if not API_TOKEN:
        print("Set VAPE_API_TOKEN environment variable first.")
        sys.exit(1)

    print(f"Dummy vape simulator — targeting {SERVER_URL}")
    print(f"Device name: {VAPE_NAME}")
    print()
    print("Commands:")
    print("  a  — coil A started (active)")
    print("  A  — coil A stopped (inactive)")
    print("  b  — coil B started (active)")
    print("  B  — coil B stopped (inactive)")
    print("  1  — both coils started")
    print("  0  — both coils stopped")
    print("  q  — quit")
    print()

    while True:
        try:
            choice = input(">> ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\nBye!")
            break

        if choice == "a":
            print("Sending coil_a started...")
            send_update("coil_a", "started")
        elif choice == "A":
            print("Sending coil_a stopped...")
            send_update("coil_a", "stopped")
        elif choice == "b":
            print("Sending coil_b started...")
            send_update("coil_b", "started")
        elif choice == "B":
            print("Sending coil_b stopped...")
            send_update("coil_b", "stopped")
        elif choice == "1":
            print("Sending both coils started...")
            send_update("coil_a", "started")
            send_update("coil_b", "started")
        elif choice == "0":
            print("Sending both coils stopped...")
            send_update("coil_a", "stopped")
            send_update("coil_b", "stopped")
        elif choice in ("q", "quit", "exit"):
            print("Bye!")
            break
        else:
            print("Unknown command. Use a/A/b/B/1/0/q")


if __name__ == "__main__":
    main()
