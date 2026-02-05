#!/usr/bin/env python3
"""
FAST Donkey Kong-style runner for e-ink display.
Now with FLIPS at corners!

Usage:
    sudo python3 runner.py /dev/sg0
"""

import sys
import time
from PIL import Image, ImageDraw

from eink import EInkDisplay, MODE_A2

# Bigger sprite with more detail
SPRITE_RUN_R = [
    "    ████████    ",
    "   ██████████   ",
    "   ███░░░░███   ",
    "   ██░██░██░██  ",
    "   ████░░░████  ",
    "    ██████████  ",
    "      ████      ",
    "    ████████    ",
    "   ██████████   ",
    "  ████ ██ ████  ",
    " ███   ██   ███ ",
    "       ██       ",
    "      ████      ",
    "     ██  ██     ",
    "    ███  ███    ",
    "   ████  ████   ",
]

SPRITE_RUN_L = [row[::-1] for row in SPRITE_RUN_R]

# Flip animation frames (somersault!)
SPRITE_FLIP_1 = [
    "                ",
    "    ████████    ",
    "   ██████████   ",
    "  ████░░░░████  ",
    "  ███░██░███░█  ",
    "  █████░░█████  ",
    "   ██████████   ",
    "  ████████████  ",
    " ██████████████ ",
    " ██ ████████ ██ ",
    "    ██    ██    ",
    "   ██      ██   ",
    "  ███      ███  ",
    "                ",
    "                ",
    "                ",
]

SPRITE_FLIP_2 = [
    "                ",
    "                ",
    "   ███    ███   ",
    "  ████    ████  ",
    " █████    █████ ",
    " ██████████████ ",
    "  ████████████  ",
    "   ██████████   ",
    "   ███░░░░███   ",
    "   ██░██░██░██  ",
    "   ████░░░████  ",
    "    ██████████  ",
    "     ████████   ",
    "                ",
    "                ",
    "                ",
]

SPRITE_FLIP_3 = [
    "                ",
    "                ",
    "                ",
    "  ███      ███  ",
    "   ██      ██   ",
    "    ██    ██    ",
    " ██ ████████ ██ ",
    " ██████████████ ",
    "  ████████████  ",
    "   ██████████   ",
    "  █████░░█████  ",
    "  ███░██░███░█  ",
    "  ████░░░░████  ",
    "   ██████████   ",
    "    ████████    ",
    "                ",
]

SPRITE_FLIP_4 = [
    "                ",
    "                ",
    "                ",
    "   ████  ████   ",
    "    ███  ███    ",
    "     ██  ██     ",
    "      ████      ",
    "       ██       ",
    " ███   ██   ███ ",
    "  ████ ██ ████  ",
    "   ██████████   ",
    "    ████████    ",
    "      ████      ",
    "    ██████████  ",
    "   ████░░░████  ",
    "   ██░██░██░██  ",
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
            elif char == '░':
                draw.rectangle([
                    x * scale, y * scale,
                    (x + 1) * scale - 1, (y + 1) * scale - 1
                ], fill=180)

    return img


class FlippingRunner:
    """Runner that does flips at corners!"""

    def __init__(self, display):
        self.display = display
        self.w = display.width
        self.h = display.height

        # Bigger sprite
        self.scale = 6
        self.sprite_right = sprite_to_image(SPRITE_RUN_R, self.scale)
        self.sprite_left = sprite_to_image(SPRITE_RUN_L, self.scale)

        # Flip frames
        self.flip_frames = [
            sprite_to_image(SPRITE_FLIP_1, self.scale),
            sprite_to_image(SPRITE_FLIP_2, self.scale),
            sprite_to_image(SPRITE_FLIP_3, self.scale),
            sprite_to_image(SPRITE_FLIP_4, self.scale),
        ]

        self.sprite_w = self.sprite_right.width
        self.sprite_h = self.sprite_right.height

        # Position
        self.x = 100
        self.y = 100
        self.direction = 'right'
        self.flipping = False
        self.flip_frame = 0

        # Movement
        self.speed = 60
        self.margin = 100

    def get_sprite(self):
        if self.flipping:
            return self.flip_frames[self.flip_frame % len(self.flip_frames)]
        if self.direction in ('right', 'down'):
            return self.sprite_right
        return self.sprite_left

    def do_flip(self):
        """Animate a flip at the corner."""
        old_x, old_y = self.x, self.y
        for i in range(len(self.flip_frames)):
            self.flip_frame = i
            self.flipping = True
            self.draw_fast(old_x, old_y)
        self.flipping = False

    def move(self):
        """Move and return old position. Do flip at corners!"""
        old_x, old_y = self.x, self.y
        did_turn = False

        if self.direction == 'right':
            self.x += self.speed
            if self.x >= self.w - self.margin - self.sprite_w:
                self.x = self.w - self.margin - self.sprite_w
                self.direction = 'down'
                did_turn = True

        elif self.direction == 'down':
            self.y += self.speed
            if self.y >= self.h - self.margin - self.sprite_h:
                self.y = self.h - self.margin - self.sprite_h
                self.direction = 'left'
                did_turn = True

        elif self.direction == 'left':
            self.x -= self.speed
            if self.x <= self.margin:
                self.x = self.margin
                self.direction = 'up'
                did_turn = True

        elif self.direction == 'up':
            self.y -= self.speed
            if self.y <= self.margin:
                self.y = self.margin
                self.direction = 'right'
                did_turn = True

        if did_turn:
            self.do_flip()

        return old_x, old_y

    def draw_fast(self, old_x, old_y):
        """Single combined region update."""
        min_x = int(min(old_x, self.x))
        min_y = int(min(old_y, self.y))
        max_x = int(max(old_x, self.x)) + self.sprite_w
        max_y = int(max(old_y, self.y)) + self.sprite_h

        region_w = max_x - min_x
        region_h = max_y - min_y

        region = Image.new('L', (region_w, region_h), 255)

        sprite = self.get_sprite()
        paste_x = int(self.x - min_x)
        paste_y = int(self.y - min_y)
        region.paste(sprite, (paste_x, paste_y))

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

    print(f"=== FLIPPY RUNNER ===")
    print(f"Display: {display.width}x{display.height}")
    print("Ctrl+C to stop\n")

    display.clear()

    runner = FlippingRunner(display)

    print("GO! Watch for flips at corners!")
    lap = 0
    frames = 0
    start = time.time()

    try:
        while True:
            old_x, old_y = runner.move()
            runner.draw_fast(old_x, old_y)
            frames += 1

            # Count laps
            if runner.direction == 'right' and runner.x <= runner.margin + runner.speed:
                if frames > 10:
                    lap += 1
                    elapsed = time.time() - start
                    fps = frames / elapsed
                    print(f"Lap {lap} | {fps:.1f} FPS | {elapsed:.1f}s")
                    frames = 0
                    start = time.time()

    except KeyboardInterrupt:
        print(f"\n\nDone! {lap} laps completed")
        display.clear()
        display.close()


if __name__ == '__main__':
    main()
