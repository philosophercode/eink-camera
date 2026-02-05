#!/usr/bin/env python3
"""
Simple example showing how to use the Python e-ink driver.
No AI dependencies - just displays images.

Usage:
    sudo python3 example_simple.py /dev/sg0
"""

import sys
import subprocess
from PIL import Image, ImageDraw, ImageFont
from eink import EInkDisplay, MODE_GC16, MODE_A2, MODE_INIT


def create_test_pattern(width, height):
    """Create a test pattern image."""
    img = Image.new('L', (width, height), 255)  # White background
    draw = ImageDraw.Draw(img)

    # Draw some shapes
    margin = 50
    draw.rectangle([margin, margin, width-margin, height-margin], outline=0, width=5)

    # Gradient bars
    bar_height = 100
    bar_y = height // 2 - bar_height // 2
    num_bars = 16
    bar_width = (width - 2*margin) // num_bars

    for i in range(num_bars):
        gray = int(255 * i / (num_bars - 1))
        x = margin + i * bar_width
        draw.rectangle([x, bar_y, x + bar_width, bar_y + bar_height], fill=gray)

    # Text
    try:
        font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 60)
    except:
        font = ImageFont.load_default()

    draw.text((width//2, 150), "E-Ink Test", anchor="mm", font=font, fill=0)
    draw.text((width//2, height-150), f"{width}x{height}", anchor="mm", font=font, fill=0)

    return img


def capture_and_display(display):
    """Capture a photo and display it."""
    print("Capturing photo...")
    tmp_path = '/tmp/test_capture.jpg'

    subprocess.run([
        'libcamera-still',
        '-o', tmp_path,
        '--width', str(display.width),
        '--height', str(display.height),
        '-t', '1',
        '--nopreview'
    ], capture_output=True)

    print("Displaying...")
    display.show_image(tmp_path, mode=MODE_GC16)
    print("Done!")


def main():
    if len(sys.argv) < 2:
        print("Usage: sudo python3 example_simple.py /dev/sgX [command]")
        print("\nCommands:")
        print("  test    - Show test pattern")
        print("  capture - Capture and display photo")
        print("  clear   - Clear display")
        print("  <file>  - Display image file")
        sys.exit(1)

    device = sys.argv[1]
    command = sys.argv[2] if len(sys.argv) > 2 else 'test'

    print(f"Opening {device}...")
    with EInkDisplay(device) as display:
        print(f"Display: {display.width}x{display.height}")

        if command == 'test':
            print("Creating test pattern...")
            img = create_test_pattern(display.width, display.height)
            print("Displaying...")
            display.show_image(img)
            print("Done!")

        elif command == 'capture':
            capture_and_display(display)

        elif command == 'clear':
            print("Clearing display...")
            display.clear(MODE_INIT)
            print("Done!")

        else:
            # Treat as filename
            print(f"Displaying {command}...")
            display.show_image(command)
            print("Done!")


if __name__ == '__main__':
    main()
