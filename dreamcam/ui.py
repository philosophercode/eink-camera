"""Screen renderer for e-ink camera UI."""

from __future__ import annotations

import time
from typing import TYPE_CHECKING

from PIL import Image, ImageDraw, ImageFont

from dreamcam.display import MODE_A2, MODE_GC16, MODE_INIT

if TYPE_CHECKING:
    from dreamcam.display import Display

# Font search paths (most common Linux locations)
FONT_PATHS = [
    "/usr/share/fonts/truetype/freefont/FreeSansBold.ttf",
    "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
]


class ScreenRenderer:
    """Renders text screens and overlays on the e-ink display."""

    def __init__(self, display: Display):
        self.display = display
        self.width = display.width
        self.height = display.height
        self._load_fonts()

    def _load_fonts(self):
        """Load fonts with fallback chain."""
        self.font_big = None
        for path in FONT_PATHS:
            try:
                self.font_big = ImageFont.truetype(path, 120)
                self.font_med = ImageFont.truetype(path, 64)
                self.font_small = ImageFont.truetype(path, 40)
                self.font_body = ImageFont.truetype(path, 36)
                break
            except (IOError, OSError):
                continue

        if self.font_big is None:
            self.font_big = ImageFont.load_default()
            self.font_med = self.font_big
            self.font_small = self.font_big
            self.font_body = self.font_big

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

    def show_qr_code(self, url: str, duration: float = 0.0):
        """Display a QR code with the URL on the e-ink screen."""
        try:
            import qrcode
        except ImportError:
            self.show_screen("Web Remote", subtitle=url)
            if duration:
                time.sleep(duration)
            return

        self.display.clear(MODE_INIT)

        qr = qrcode.QRCode(box_size=1, border=2,
                            error_correction=qrcode.constants.ERROR_CORRECT_M)
        qr.add_data(url)
        qr.make(fit=True)
        qr_img = qr.make_image(fill_color="black", back_color="white")
        qr_img = qr_img.convert('L')

        # Scale QR to fit nicely on the e-ink display
        qr_size = min(self.height - 300, 700)
        qr_img = qr_img.resize((qr_size, qr_size), Image.Resampling.NEAREST)

        img = Image.new('L', (self.width, self.height), 255)
        draw = ImageDraw.Draw(img)

        # Title
        draw.text((self.width // 2, 80), "SCAN TO CONNECT",
                  anchor="mm", font=self.font_med, fill=0)

        # QR code centered
        qr_x = (self.width - qr_size) // 2
        qr_y = (self.height - qr_size) // 2 + 20
        img.paste(qr_img, (qr_x, qr_y))

        # URL below QR
        draw.text((self.width // 2, qr_y + qr_size + 40), url,
                  anchor="mm", font=self.font_small, fill=80)

        self.display.show_image(img, mode=MODE_GC16)
        if duration:
            time.sleep(duration)

    def show_capture_mode(self):
        """Idle screen with instructions."""
        self.show_screen(
            "Capture",
            subtitle="Press to capture",
            body="2x: styles | Hold: switch mode",
        )

    def show_gallery_mode(self, total_images):
        self.show_screen("Gallery", subtitle=f"{total_images} images",
                         body="Click: next | 2x: prev | Hold: switch")
        time.sleep(2)

    def show_slideshow_mode(self, total_images):
        self.show_screen("Slideshow", subtitle=f"{total_images} images",
                         body="Click: pause/play | Hold: switch")
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

    def show_style_carousel(self, names, descs, current_idx, first_frame=False):
        """Vertical carousel: prev / CURRENT / next."""
        total = len(names)
        prev_idx = (current_idx - 1) % total
        next_idx = (current_idx + 1) % total

        if first_frame:
            self.display.clear(MODE_INIT)

        img = Image.new('L', (self.width, self.height), 255)
        draw = ImageDraw.Draw(img)
        cy = self.height // 2

        # Previous (faded)
        draw.text((self.width // 2, cy - 250),
                  names[prev_idx].upper(),
                  anchor="mm", font=self.font_med, fill=180)
        draw.line([(300, cy - 150), (self.width - 300, cy - 150)], fill=160, width=2)

        # Current (bold)
        draw.text((self.width // 2, cy - 30),
                  names[current_idx].upper(),
                  anchor="mm", font=self.font_big, fill=0)
        # Description
        short_desc = descs[current_idx][:55] + "..."
        draw.text((self.width // 2, cy + 70),
                  short_desc, anchor="mm", font=self.font_small, fill=100)

        draw.line([(300, cy + 150), (self.width - 300, cy + 150)], fill=160, width=2)

        # Next (faded)
        draw.text((self.width // 2, cy + 250),
                  names[next_idx].upper(),
                  anchor="mm", font=self.font_med, fill=180)

        self.display.show_image(img, mode=MODE_A2)

    def show_text_result(self, mode_name, text):
        """Display AI-generated text with title and word-wrapped body."""
        self.display.clear(MODE_INIT)

        img = Image.new('L', (self.width, self.height), 255)
        draw = ImageDraw.Draw(img)

        margin = 100
        max_text_width = self.width - margin * 2

        title_y = 80
        draw.text((self.width // 2, title_y), mode_name.upper(),
                  anchor="mm", font=self.font_med, fill=0)

        divider_y = title_y + 50
        draw.line([(margin, divider_y), (self.width - margin, divider_y)],
                  fill=120, width=2)

        body_y = divider_y + 40
        lines = self._wrap_text(text, self.font_body, max_text_width)
        line_height = 48

        for line in lines:
            if body_y + line_height > self.height - 40:
                break
            draw.text((margin, body_y), line, font=self.font_body, fill=30)
            body_y += line_height

        self.display.show_image(img, mode=MODE_GC16)

    def _wrap_text(self, text, font, max_width):
        """Word-wrap text to fit within max_width pixels."""
        lines = []
        for paragraph in text.split('\n'):
            if not paragraph.strip():
                lines.append('')
                continue
            words = paragraph.split()
            if not words:
                lines.append('')
                continue
            current_line = words[0]
            for word in words[1:]:
                test = current_line + ' ' + word
                if font.getlength(test) <= max_width:
                    current_line = test
                else:
                    lines.append(current_line)
                    current_line = word
            lines.append(current_line)
        return lines
