#!/usr/bin/env python3
"""Screen renderer for e-ink camera UI."""

import time
from PIL import Image, ImageDraw, ImageFont

from eink import MODE_A2, MODE_INIT


class ScreenRenderer:
    """Renders text screens and overlays on the e-ink display."""

    def __init__(self, display):
        self.display = display
        self.width = display.width
        self.height = display.height
        self._load_fonts()

    def _load_fonts(self):
        """Load fonts with fallback chain."""
        font_paths = [
            "/usr/share/fonts/truetype/freefont/FreeSansBold.ttf",
            "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
        ]
        self.font_big = None
        self.font_med = None
        self.font_small = None

        for path in font_paths:
            try:
                self.font_big = ImageFont.truetype(path, 120)
                self.font_med = ImageFont.truetype(path, 64)
                self.font_small = ImageFont.truetype(path, 40)
                break
            except (IOError, OSError):
                continue

        # PIL default fallback
        if self.font_big is None:
            self.font_big = ImageFont.load_default()
            self.font_med = self.font_big
            self.font_small = self.font_big

    def show_screen(self, title, subtitle=None, body=None, mode=MODE_A2):
        """General centered text screen. Full clear first to prevent ghosting."""
        self.display.clear(MODE_INIT)

        img = Image.new('L', (self.width, self.height), 255)
        draw = ImageDraw.Draw(img)

        y_title = self.height // 2 - 80 if (subtitle or body) else self.height // 2
        draw.text((self.width // 2, y_title), title,
                  anchor="mm", font=self.font_big, fill=0)

        if subtitle:
            draw.text((self.width // 2, y_title + 100), subtitle,
                      anchor="mm", font=self.font_med, fill=60)

        if body:
            draw.text((self.width // 2, y_title + 180), body,
                      anchor="mm", font=self.font_small, fill=100)

        self.display.show_image(img, mode=mode)

    def show_splash(self, text="Digital Polaroid", duration=2.5):
        """Timed splash screen."""
        self.show_screen(text)
        time.sleep(duration)

    def show_capture_mode(self):
        """Idle screen with instructions."""
        self.show_screen(
            "Capture",
            subtitle="Press to capture",
            body="2x: styles | Hold: switch mode",
        )

    def show_gallery_mode(self, total_images):
        """Gallery entry screen."""
        self.show_screen(
            "Gallery",
            subtitle=f"{total_images} images",
            body="Click: next | 2x: prev | Hold: switch",
        )
        time.sleep(2)

    def show_slideshow_mode(self, total_images):
        """Slideshow entry screen."""
        self.show_screen(
            "Slideshow",
            subtitle=f"{total_images} images",
            body="Click: pause/play | Hold: switch",
        )
        time.sleep(2)

    def show_overlay(self, text, duration=1.0):
        """Brief text overlay for status feedback."""
        band_h = 160
        band_y = (self.height - band_h) // 2
        img = Image.new('L', (self.width, band_h), 255)
        draw = ImageDraw.Draw(img)
        draw.text((self.width // 2, band_h // 2), text,
                  anchor="mm", font=self.font_big, fill=0)

        self.display.display(img.tobytes(), x=0, y=band_y,
                             w=self.width, h=band_h, mode=MODE_A2)
        time.sleep(duration)

    def show_style_carousel(self, style_names, style_descs, current_idx, first_frame=False):
        """
        Vertical carousel: prev / CURRENT / next style.

        MODE_INIT on first frame for clean entry, MODE_A2 for cycling.
        """
        total = len(style_names)
        prev_idx = (current_idx - 1) % total
        next_idx = (current_idx + 1) % total

        if first_frame:
            self.display.clear(MODE_INIT)

        img = Image.new('L', (self.width, self.height), 255)
        draw = ImageDraw.Draw(img)
        cy = self.height // 2

        # Previous style (faded)
        draw.text((self.width // 2, cy - 250),
                  style_names[prev_idx].upper(),
                  anchor="mm", font=self.font_med, fill=180)

        draw.line([(300, cy - 150), (self.width - 300, cy - 150)], fill=160, width=2)

        # Current style (bold)
        draw.text((self.width // 2, cy - 30),
                  style_names[current_idx].upper(),
                  anchor="mm", font=self.font_big, fill=0)

        # Description
        short_desc = style_descs[current_idx][:55] + "..."
        draw.text((self.width // 2, cy + 70),
                  short_desc, anchor="mm", font=self.font_small, fill=100)

        draw.line([(300, cy + 150), (self.width - 300, cy + 150)], fill=160, width=2)

        # Next style (faded)
        draw.text((self.width // 2, cy + 250),
                  style_names[next_idx].upper(),
                  anchor="mm", font=self.font_med, fill=180)

        self.display.show_image(img, mode=MODE_A2)
