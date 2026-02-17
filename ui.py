#!/usr/bin/env python3
"""Screen renderer for e-ink camera UI."""

import time
from PIL import Image, ImageDraw, ImageFont

from eink import MODE_A2


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
        """General centered text screen. Clears display first to prevent ghosting."""
        self.display.clear(MODE_A2)

        img = Image.new('L', (self.width, self.height), 255)
        draw = ImageDraw.Draw(img)

        # Title centered vertically (offset up if there's more text)
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
            "Capture Mode",
            subtitle="Press trigger to capture",
            body="Hold: styles | Triple-click: gallery",
        )

    def show_gallery_splash(self, total_images):
        """Gallery entry splash with nav instructions."""
        self.show_screen(
            "Gallery Mode",
            subtitle=f"{total_images} images",
            body="Click: play/pause | 2x click: back | Hold: exit",
        )
        time.sleep(3)

    def show_overlay(self, text, duration=1.0):
        """Brief text overlay for status feedback (e.g. 'Paused')."""
        # Render overlay in center band
        band_h = 160
        band_y = (self.height - band_h) // 2
        img = Image.new('L', (self.width, band_h), 255)
        draw = ImageDraw.Draw(img)
        draw.text((self.width // 2, band_h // 2), text,
                  anchor="mm", font=self.font_big, fill=0)

        self.display.display(img.tobytes(), x=0, y=band_y,
                             w=self.width, h=band_h, mode=MODE_A2)
        time.sleep(duration)

    def show_style_banner(self, name, desc):
        """Show style name and description. Clears display first."""
        self.display.clear(MODE_A2)

        img = Image.new('L', (self.width, self.height), 255)
        draw = ImageDraw.Draw(img)

        draw.text((self.width // 2, self.height // 2 - 50),
                  f"[ {name.upper()} ]", anchor="mm", font=self.font_big, fill=0)

        short_desc = desc[:60] + "..."
        draw.text((self.width // 2, self.height // 2 + 80),
                  short_desc, anchor="mm", font=self.font_small, fill=80)

        self.display.show_image(img, mode=MODE_A2)
