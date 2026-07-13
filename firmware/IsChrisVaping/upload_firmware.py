#!/usr/bin/env python3
"""Compile and upload firmware to the vape server for OTA updates."""

import argparse
import os
import re
import subprocess
import sys

import requests

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
VERSION_H = os.path.join(SCRIPT_DIR, "version.h")
PROJECT_DIR = os.path.dirname(SCRIPT_DIR)  # firmware/ directory containing platformio.ini

VARIANTS = ["esp32", "esp32_4mb"]


def read_version():
    """Read the current version from version.h."""
    with open(VERSION_H, "r") as f:
        content = f.read()
    match = re.search(r'#define FIRMWARE_VERSION "(\d+)\.(\d+)\.(\d+)"', content)
    if not match:
        print("Error: could not parse version from version.h", file=sys.stderr)
        sys.exit(1)
    return int(match.group(1)), int(match.group(2)), int(match.group(3))


def write_version(major, minor, patch):
    """Write the new version to version.h."""
    with open(VERSION_H, "w") as f:
        f.write(f'// Firmware version\n#define FIRMWARE_VERSION "{major}.{minor}.{patch}"\n')


def bump_version(bump_type):
    """Bump the version according to bump_type and return the new version string."""
    major, minor, patch = read_version()
    if bump_type == "MAJOR":
        major += 1
        minor = 0
        patch = 0
    elif bump_type == "MINOR":
        minor += 1
        patch = 0
    elif bump_type == "PATCH":
        patch += 1
    write_version(major, minor, patch)
    return f"{major}.{minor}.{patch}"


def compile_firmware(variant):
    """Compile the firmware for a given variant and return the path to the .bin file."""
    print(f"Compiling firmware for variant '{variant}'...")
    env = os.environ.copy()
    env["IDF_COMPONENT_MANAGER"] = "0"
    result = subprocess.run(
        ["pio", "run", "-e", variant],
        cwd=PROJECT_DIR,
        env=env,
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        print(f"Compilation failed for {variant}:\n{result.stderr}", file=sys.stderr)
        sys.exit(1)
    print(result.stdout)

    bin_path = os.path.join(PROJECT_DIR, ".pio", "build", variant, "firmware.bin")
    if not os.path.isfile(bin_path):
        print(f"Error: compiled binary not found at {bin_path}", file=sys.stderr)
        sys.exit(1)
    return bin_path


def upload_firmware(firmware_path, version, variant, server, token):
    """Upload the compiled firmware to the server."""
    print(f"Uploading v{version} ({variant}) to {server}...")
    with open(firmware_path, "rb") as f:
        files = {"file": (os.path.basename(firmware_path), f, "application/octet-stream")}
        response = requests.post(
            f"{server.rstrip('/')}/firmware/upload",
            data={"version": version, "variant": variant},
            headers={"Authorization": f"Bearer {token}"},
            files=files,
        )

    if response.status_code == 200:
        data = response.json()
        print(f"Upload successful: v{data['version']} variant={data['variant']} ({data['size']} bytes)")
    else:
        print(f"Upload failed ({response.status_code}): {response.text}", file=sys.stderr)
        sys.exit(1)


def main():
    parser = argparse.ArgumentParser(description="Compile and upload firmware to OTA server")
    version_group = parser.add_mutually_exclusive_group(required=True)
    version_group.add_argument("--version", help="Firmware version (e.g. 1.2.0)")
    version_group.add_argument(
        "--bump", choices=["MAJOR", "MINOR", "PATCH"],
        help="Bump version in version.h (MAJOR, MINOR, or PATCH)",
    )
    parser.add_argument("--server", required=True, help="Server base URL (e.g. https://example.com)")
    parser.add_argument("--token", required=True, help="API auth token")
    parser.add_argument(
        "--variant", choices=VARIANTS, action="append",
        help="Variant(s) to build and upload (default: all). Can be specified multiple times.",
    )
    args = parser.parse_args()

    # Determine version
    if args.bump:
        version = bump_version(args.bump)
        print(f"Bumped version to {version}")
    else:
        version = args.version
        # Also update version.h to match the explicit version
        parts = version.split(".")
        if len(parts) != 3 or not all(p.isdigit() for p in parts):
            print("Error: version must be in MAJOR.MINOR.PATCH format", file=sys.stderr)
            sys.exit(1)
        write_version(int(parts[0]), int(parts[1]), int(parts[2]))

    variants = args.variant if args.variant else VARIANTS

    # Compile and upload each variant
    for variant in variants:
        firmware_path = compile_firmware(variant)
        upload_firmware(firmware_path, version, variant, args.server, args.token)

    print(f"\nAll done! v{version} uploaded for: {', '.join(variants)}")


if __name__ == "__main__":
    main()
