#!/usr/bin/env python3
"""Gallery browser for saved dream images."""

import os
import time
import glob as _glob

from eink import MODE_GC16


class GalleryBrowser:
    """Browse saved dream images with slideshow support."""

    def __init__(self, display, screen, dreams_dir):
        self.display = display
        self.screen = screen
        self.dreams_dir = dreams_dir
        self.images = []

    def load_images(self):
        """Scan dreams dir, filter originals, sort newest first."""
        if not self.dreams_dir or not os.path.isdir(self.dreams_dir):
            return []
        files = sorted(_glob.glob(os.path.join(self.dreams_dir, '*.jpg')))
        self.images = [f for f in files if '_original.' not in os.path.basename(f)]
        self.images.reverse()  # Most recent first
        return self.images

    def _show_image(self, idx):
        """Display image at index, skip corrupt files."""
        name = os.path.basename(self.images[idx])
        total = len(self.images)
        print(f"\r  {idx+1}/{total}: {name}\r\n", end='', flush=True)
        try:
            self.display.show_image(self.images[idx], mode=MODE_GC16)
            return True
        except Exception:
            print(f"\r  (skipping corrupt file)\r\n", end='', flush=True)
            return False

    def run(self, gpio_chip=None, gpio_pin=None):
        """
        Main gallery loop.

        Controls:
          - Single click: toggle slideshow on/off
          - Double click: previous image (also pauses)
          - Long press (1.5s): exit gallery

        Returns when user exits.
        """
        images = self.load_images()
        if not images:
            print("\rNo dreams saved\r\n", end='', flush=True)
            return

        total = len(images)
        self.screen.show_gallery_splash(total)

        idx = 0
        slideshow = False
        last_advance = time.time()

        self._show_image(idx)

        # GPIO state
        last_btn = 1
        btn_time = 0
        click_count = 0
        last_click_time = 0

        while True:
            now = time.time()

            # Auto-advance in slideshow mode
            if slideshow and now - last_advance >= 60:
                idx = (idx + 1) % total
                self._show_image(idx)
                last_advance = now

            if gpio_chip is not None:
                import lgpio
                state = lgpio.gpio_read(gpio_chip, gpio_pin)

                if last_btn == 1 and state == 0:
                    # Button pressed
                    btn_time = now
                elif last_btn == 0 and state == 1:
                    # Button released
                    hold_duration = now - btn_time
                    if hold_duration >= 1.5:
                        # Long press - exit gallery
                        break
                    else:
                        click_count += 1
                        last_click_time = now

                last_btn = state

                # Process clicks after timeout
                if click_count > 0 and now - last_click_time > 0.4:
                    if click_count == 1:
                        # Single click - toggle slideshow
                        slideshow = not slideshow
                        if slideshow:
                            self.screen.show_overlay("Slideshow", duration=0.8)
                            self._show_image(idx)  # Restore image after overlay
                            last_advance = now
                        else:
                            self.screen.show_overlay("Paused", duration=0.8)
                            self._show_image(idx)
                    elif click_count >= 2:
                        # Double click - previous image (and pause)
                        slideshow = False
                        idx = (idx - 1) % total
                        self._show_image(idx)
                    click_count = 0

            # Also check keyboard if TTY is available
            try:
                import select, sys
                if select.select([sys.stdin], [], [], 0.05)[0]:
                    key = sys.stdin.read(1)
                    if key in ('q', 'g'):
                        break
                    elif key == ' ':
                        # Space toggles slideshow
                        slideshow = not slideshow
                        if slideshow:
                            self.screen.show_overlay("Slideshow", duration=0.8)
                            self._show_image(idx)
                            last_advance = now
                        else:
                            self.screen.show_overlay("Paused", duration=0.8)
                            self._show_image(idx)
                    elif key == 'p':
                        # Previous
                        slideshow = False
                        idx = (idx - 1) % total
                        self._show_image(idx)
                    elif key == 'n':
                        # Next
                        idx = (idx + 1) % total
                        self._show_image(idx)
                        last_advance = now
            except (termios_error, ValueError):
                # No TTY available - just sleep for polling
                time.sleep(0.05)

        print("\r[Exit gallery]\r\n", end='', flush=True)


# Exception alias for TTY check
try:
    import termios
    termios_error = termios.error
except ImportError:
    termios_error = OSError
