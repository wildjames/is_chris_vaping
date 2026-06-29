#!/usr/bin/env python3
"""Generate a QR code containing the server URL and auth token for the IsChrisVaping app."""

import argparse
import json

import qrcode


def main():
    parser = argparse.ArgumentParser(description="Generate config QR code for IsChrisVaping app")
    parser.add_argument("--url", required=True, help="Server base URL (e.g. https://example.com)")
    parser.add_argument("--token", required=True, help="Auth token")
    parser.add_argument("--output", default="vape_config_qr.png", help="Output filename (default: vape_config_qr.png)")
    args = parser.parse_args()

    payload = json.dumps({"server_url": args.url, "auth_token": args.token})

    img = qrcode.make(payload)
    img.save(args.output)
    print(f"QR code saved to {args.output}")


if __name__ == "__main__":
    main()
