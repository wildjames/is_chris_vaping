"""
Converts PNG images to 1-bit packed C arrays for use with a 170x320 TFT display.
Images are thresholded to black/white and stored as packed bits (MSB first).

Usage:
    python png_to_array.py input.png -o output.h
    python png_to_array.py input.png --name my_image -o output.h
    python png_to_array.py input.png --no-resize
"""

import argparse
from pathlib import Path
from PIL import Image


DISPLAY_WIDTH = 170
DISPLAY_HEIGHT = 320


def convert_image(image_path, array_name):
    img = Image.open(image_path).convert("L")  # grayscale

    width, height = img.size
    pixels = list(img.getdata())

    print(f"Original image size: {width}x{height}")

    if width == DISPLAY_HEIGHT and height == DISPLAY_WIDTH:
        # Rotate 90 degrees
        print("Rotating image 90 degrees to fit display...")
        img = img.rotate(-90, expand=True)
        width, height = img.size
        pixels = list(img.getdata())
        print(f"New image size: {width}x{height}")

    # Pack pixels into bytes (MSB first), 1 = white, 0 = black
    packed = []
    for i in range(0, len(pixels), 8):
        byte = 0
        for bit in range(8):
            idx = i + bit
            if idx < len(pixels) and pixels[idx] >= 128:
                byte |= (0x80 >> bit)
        packed.append(byte)

    lines = []
    lines.append(f"// Generated from {Path(image_path).name}")
    lines.append(f"// {width}x{height} 1-bit packed (MSB first)")
    lines.append(f"#pragma once")
    lines.append(f"#include <stdint.h>")
    lines.append(f"")
    lines.append(f"const uint16_t {array_name}_width = {width};")
    lines.append(f"const uint16_t {array_name}_height = {height};")
    lines.append(f"const uint8_t {array_name}[] PROGMEM = {{")

    # Format 16 bytes per line
    for i in range(0, len(packed), 16):
        chunk = packed[i:i+16]
        vals = [f"0x{b:02X}" for b in chunk]
        lines.append("  " + ", ".join(vals) + ",")

    lines.append("};")
    lines.append("")

    return "\n".join(lines)


def main():
    parser = argparse.ArgumentParser(description="Convert PNG to RGB565 Arduino array")
    parser.add_argument("input", help="Input PNG file")
    parser.add_argument("-o", "--output", help="Output header file (default: stdout)")
    parser.add_argument("--name", help="Array variable name (default: derived from filename)")
    args = parser.parse_args()

    array_name = args.name
    if not array_name:
        array_name = Path(args.input).stem.replace("-", "_").replace(" ", "_")
        # Ensure valid C identifier
        if array_name[0].isdigit():
            array_name = "img_" + array_name

    result = convert_image(args.input, array_name)

    if args.output:
        Path(args.output).write_text(result)
        print(f"Written to {args.output}")
    else:
        print(result)


if __name__ == "__main__":
    main()
