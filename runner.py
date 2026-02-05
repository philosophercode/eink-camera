#!/usr/bin/env python3
"""
FAST Donkey Kong-style runner for e-ink display.
Optimized for maximum speed with A2 partial refresh.

Usage:
    sudo python3 runner.py /dev/sg0
"""

import os
import sys
import time
from PIL import Image, ImageDraw

from eink import EInkDisplay, MODE_A2

# Tiny sprite (8x8) for faster refresh - smaller = faster!
SPRITE_R = [
    " ██  ",
    "████ ",
    " ██  ",
    "████ ",
    " █ █ ",
    "█   █",
]

SPRITE_L = [
    "  ██ ",
    " ████",
    "  ██ ",
    " ████",
    " █ █ ",
    "█   █",
]


def sprite_to_image(sprite_data, scale=6):
    """Convert ASCII sprite to PIL Image."""
    h = len(sprite_data)
    w = max(len(row) for row in sprite_data)

    img = Image.new('L', (w * scale, h * scale), 255)
    draw = ImageDraw.Draw(img)

    for y, row in enumerate(sprite_data):
        for x, char in enumerate(row):
            if char == '█':
                draw.rectangle([
                    x * scale, y * scale,
                    (x + 1) * scale - 1, (y + 1) * scale - 1
                ], fill=0)

    return img


class FastRunner:
    """Optimized runner - single combined update region."""

    def __init__(self, display):
        self.display = display
        self.w = display.width
        self.h = display.height

        # Small sprite = fast refresh
        self.scale = 8
        self.sprite_right = sprite_to_image(SPRITE_R, self.scale)
        self.sprite_left = sprite_to_image(SPRITE_L, self.scale)
        self.sprite_w = self.sprite_right.width
        self.sprite_h = self.sprite_right.height

        # Position
        self.x = 100
        self.y = 100
        self.direction = 'right'

        # BIG steps = fewer updates = faster lap
        self.speed = 80
        self.margin = 80

    def get_sprite(self):
        if self.direction in ('right', 'down'):
            return self.sprite_right
        return self.sprite_left

    def move(self):
        """Move and return old position."""
        old_x, old_y = self.x, self.y

        if self.direction == 'right':
            self.x += self.speed
            if self.x >= self.w - self.margin - self.sprite_w:
                self.x = self.w - self.margin - self.sprite_w
                self.direction = 'down'

        elif self.direction == 'down':
            self.y += self.speed
            if self.y >= self.h - self.margin - self.sprite_h:
                self.y = self.h - self.margin - self.sprite_h
                self.direction = 'left'

        elif self.direction == 'left':
            self.x -= self.speed
            if self.x <= self.margin:
                self.x = self.margin
                self.direction = 'up'

        elif self.direction == 'up':
            self.y -= self.speed
            if self.y <= self.margin:
                self.y = self.margin
                self.direction = 'right'

        return old_x, old_y

    def draw_fast(self, old_x, old_y):
        """Single combined region update - clear old + draw new in one refresh."""
        # Calculate bounding box that covers both old and new positions
        min_x = int(min(old_x, self.x))
        min_y = int(min(old_y, self.y))
        max_x = int(max(old_x, self.x)) + self.sprite_w
        max_y = int(max(old_y, self.y)) + self.sprite_h

        region_w = max_x - min_x
        region_h = max_y - min_y

        # Create region with white background
        region = Image.new('L', (region_w, region_h), 255)

        # Paste sprite at new position (relative to region)
        sprite = self.get_sprite()
        paste_x = int(self.x - min_x)
        paste_y = int(self.y - min_y)
        region.paste(sprite, (paste_x, paste_y))

        # Single update!
        self.display.display(
            region.tobytes(),
            x=min_x, y=min_y,
            w=region_w, h=region_h,
            mode=MODE_A2
        )


def main():
    if len(sys.argv) < 2:
        print("Usage: sudo python3 runner.py /dev/sgX")
        sys.exit(1)

    device = sys.argv[1]
    display = EInkDisplay(device)

    print(f"=== FAST E-INK RUNNER ===")
    print(f"Display: {display.width}x{display.height}")
    print("Ctrl+C to stop\n")

    # Clear display first
    display.clear()

    runner = FastRunner(display)

    print("GO!")
    lap = 0
    frames = 0
    start = time.time()
    last_corner = None

    try:
        while True:
            old_x, old_y = runner.move()
            runner.draw_fast(old_x, old_y)
            frames += 1

            # Detect lap completion (back to top-left going right)
            corner = (runner.direction, runner.x <= runner.margin + runner.speed)
            if runner.direction == 'right' and runner.x == runner.margin + runner.speed and last_corner != corner:
                if frames > 4:
                    lap += 1
                    elapsed = time.time() - start
                    fps = frames / elapsed
                    print(f"Lap {lap} | {fps:.1f} FPS | {elapsed:.1f}s total")
            last_corner = corner

            # NO SLEEP - go as fast as the display allows!

    except KeyboardInterrupt:
        elapsed = time.time() - start
        fps = frames / elapsed
        print(f"\n\nStats: {frames} frames, {lap} laps, {fps:.1f} FPS avg")
        display.clear()
        display.close()


if __name__ == '__main__':
    main()
