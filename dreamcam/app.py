"""
Dream Camera application — the thin orchestrator.

Wires together display, transformer, input, UI, and gallery.
All business logic lives in the modules; this class manages
the mode state machine and the capture-dream-display pipeline.
"""

from __future__ import annotations

import math
import os
import subprocess
import threading
import time
from datetime import datetime

from PIL import Image, ImageDraw

from dreamcam.display import Display, MODE_A2, MODE_GC16, create_display
from dreamcam.gallery import Gallery
from dreamcam.input import (CLICK, DOUBLE_CLICK, HOLD, KEY_CLEAR, KEY_MODE,
                             KEY_RESET, KEY_STYLE, QUIT, WEB_SET_STYLE,
                             WEB_UPLOAD, InputManager)
from dreamcam.styles import (DEFAULT_STYLE, STYLES, Style, get_style,
                              style_names, style_prompts)
from dreamcam.transform import Transformer
from dreamcam.ui import ScreenRenderer

# Operational modes
MODE_CAPTURE = 'capture'
MODE_GALLERY = 'gallery'
MODE_SLIDESHOW = 'slideshow'

MODE_NAMES = ['Capture', 'Gallery', 'Slideshow']
MODE_DESCS = ['Take AI dream photos', 'Browse dreams manually', 'Auto-play every 60s']
MODE_KEYS = [MODE_CAPTURE, MODE_GALLERY, MODE_SLIDESHOW]

# Timing
SLIDESHOW_INTERVAL = 60     # Seconds between auto-advance
CAROUSEL_INTERVAL = 2.0     # Seconds between style carousel auto-advance
AUTO_RESET_INTERVAL = 10    # Captures before auto-reset
SPINNER_SIZE = 120          # Spinner animation size in pixels


class DreamCamera:
    """AI-powered camera that reimagines what it sees."""

    def __init__(self, display: Display, transformer: Transformer,
                 save_dir: str | None = None):
        self.display = display
        self.transformer = transformer
        self.screen = ScreenRenderer(display)
        self.gallery = Gallery(save_dir)
        self.save_dir = save_dir
        self.style: Style = get_style(DEFAULT_STYLE)
        self.last_image: Image.Image | None = None
        self.capture_count = 0

        if save_dir:
            os.makedirs(save_dir, exist_ok=True)
            print(f"Saving images to: {save_dir}")

    # --- Pipeline ---

    def capture_photo(self) -> Image.Image:
        """Capture a photo using libcamera."""
        tmp_path = '/tmp/capture.jpg'
        subprocess.run([
            'libcamera-still', '-o', tmp_path,
            '--width', str(self.display.width),
            '--height', str(self.display.height),
            '-t', '1', '--nopreview'
        ], capture_output=True)
        return Image.open(tmp_path)

    def dream_and_display(self):
        """Full pipeline: capture -> show preview -> AI transform -> display."""
        print("\rCapturing...\r\n", end='', flush=True)
        photo = self.capture_photo()

        # Show captured photo immediately as preview
        preview = photo.convert('L').resize((self.display.width, self.display.height))
        self.display.show_image(preview, mode=MODE_A2)

        if self.style.is_text_mode:
            self._process_text_mode(photo)
        else:
            self._process_image_mode(photo)

        self.capture_count += 1
        self._maybe_auto_reset()

    def dream_and_display_image(self, image: Image.Image):
        """Pipeline for an externally-provided image (e.g., phone upload).

        Same as dream_and_display but skips libcamera capture.
        """
        preview = image.convert('L').resize((self.display.width, self.display.height))
        self.display.show_image(preview, mode=MODE_A2)

        if self.style.is_text_mode:
            self._process_text_mode(image)
        else:
            self._process_image_mode(image)

        self.capture_count += 1
        self._maybe_auto_reset()

    def _maybe_auto_reset(self):
        """Auto-reset display to prevent e-ink freezing."""
        if self.capture_count % AUTO_RESET_INTERVAL == 0:
            print("\r[Auto-reset to prevent freeze]\r\n", end='', flush=True)
            self.display.reset()
            if self.last_image:
                self.display.show_image(self.last_image, mode=MODE_GC16)

    def _process_text_mode(self, photo: Image.Image):
        """Generate and display AI text about the photo."""
        print(f"\rGenerating {self.style.name}...\r\n", end='', flush=True)

        result, error, elapsed = self._run_with_spinner(
            lambda: self.transformer.generate_text(photo, self.style))

        if error:
            print(f"\rError: {error}\r\n", end='', flush=True)
            return

        print(f"\rGenerate time: {elapsed:.1f}s\r\n", end='', flush=True)
        self.screen.show_text_result(self.style.name, result)
        self._save_text(photo, result)
        self.last_image = None
        print("\rDone!\r\n", end='', flush=True)

    def _process_image_mode(self, photo: Image.Image):
        """Generate and display AI-transformed image."""
        print("\rProcessing with AI...\r\n", end='', flush=True)

        result, error, elapsed = self._run_with_spinner(
            lambda: self.transformer.dream(photo, self.style))

        if error:
            print(f"\rError: {error}\r\n", end='', flush=True)
            return

        print(f"\rDream time: {elapsed:.1f}s\r\n", end='', flush=True)
        self._save_images(photo, result)

        final = result.convert('L').resize(
            (self.display.width, self.display.height), Image.Resampling.LANCZOS)
        self.display.show_image(final, mode=MODE_GC16)
        self.last_image = final
        print("\rDone!\r\n", end='', flush=True)

    def _run_with_spinner(self, fn):
        """Run fn() in a thread while showing a spinner. Returns (result, error, elapsed)."""
        result = [None]
        error = [None]

        def worker():
            try:
                result[0] = fn()
            except Exception as e:
                error[0] = e

        thread = threading.Thread(target=worker)
        thread.start()

        spinner_x = self.display.width - SPINNER_SIZE - 30
        spinner_y = 30
        start = time.time()
        frame = 0

        while thread.is_alive():
            spinner = self._spinner_frame(frame)
            self.display.display(spinner.tobytes(), x=spinner_x, y=spinner_y,
                                 w=SPINNER_SIZE, h=SPINNER_SIZE, mode=MODE_A2)
            frame += 1
            time.sleep(0.2)

        thread.join()
        return result[0], error[0], time.time() - start

    def _spinner_frame(self, frame: int) -> Image.Image:
        """Create a spinning circle indicator."""
        region = Image.new('L', (SPINNER_SIZE, SPINNER_SIZE), 255)
        draw = ImageDraw.Draw(region)
        cx = cy = SPINNER_SIZE // 2
        radius = 40

        draw.ellipse([cx - radius, cy - radius, cx + radius, cy + radius],
                     outline=180, width=6)
        start_angle = (frame * 45) % 360
        draw.arc([cx - radius, cy - radius, cx + radius, cy + radius],
                 start=start_angle, end=start_angle + 90, fill=0, width=8)
        return region

    # --- Persistence ---

    def _save_images(self, original: Image.Image, dreamed: Image.Image):
        if not self.save_dir:
            return
        ts = datetime.now().strftime('%Y-%m-%d_%H-%M-%S')
        for suffix, img in [('_original.jpg', original), (f'_{self.style.name}.jpg', dreamed)]:
            path = os.path.join(self.save_dir, f"{ts}{suffix}")
            img.convert('RGB').save(path, quality=95)
            print(f"\rSaved: {os.path.basename(path)}\r\n", end='', flush=True)

    def _save_text(self, original: Image.Image, text: str):
        if not self.save_dir:
            return
        ts = datetime.now().strftime('%Y-%m-%d_%H-%M-%S')
        orig_path = os.path.join(self.save_dir, f"{ts}_original.jpg")
        original.convert('RGB').save(orig_path, quality=95)
        text_path = os.path.join(self.save_dir, f"{ts}_{self.style.name}.txt")
        with open(text_path, 'w') as f:
            f.write(text)
        print(f"\rSaved: {os.path.basename(orig_path)}\r\n", end='', flush=True)
        print(f"\rSaved: {os.path.basename(text_path)}\r\n", end='', flush=True)

    # --- Main loop ---

    def run(self, gpio_pin: int | None = None, web_bridge=None):
        """Interactive main loop with capture, gallery, and slideshow modes."""
        print(f"\n=== AI Dream Camera ===")
        print(f"Display: {self.display.width}x{self.display.height}")
        print(f"Style: {self.style.name}")
        print("\nControls:")
        print("  Click / 1    - Capture / next / pause")
        print("  2x click / g - Styles / prev")
        print("  Hold / m     - Switch mode")
        print("  c - Clear | r - Reset | q - Quit\n")

        self.screen.show_splash("Digital Polaroid", duration=2.5)
        self.screen.show_capture_mode()

        mode = MODE_CAPTURE
        last_advance = time.time()
        slideshow_paused = False

        # Style browsing state
        style_browsing = False
        style_browse_idx = 0
        style_browse_last_advance = 0.0
        style_before_browse: str | None = None

        # Mode carousel state
        mode_carousel_active = False
        mode_carousel_idx = 0
        mode_carousel_last_advance = 0.0

        names = style_names()
        prompts = style_prompts()

        with InputManager(gpio_pin=gpio_pin, web_bridge=web_bridge) as inp:
            while True:
                now = time.time()

                # Slideshow auto-advance
                if (mode == MODE_SLIDESHOW and self.gallery.images
                        and not slideshow_paused
                        and now - last_advance >= SLIDESHOW_INTERVAL):
                    self.gallery.next(self.display)
                    last_advance = now

                # Style browsing auto-advance
                if style_browsing and now - style_browse_last_advance >= CAROUSEL_INTERVAL:
                    style_browse_idx = (style_browse_idx + 1) % len(names)
                    style_browse_last_advance = now
                    self.screen.show_style_carousel(names, prompts, style_browse_idx)

                # Mode carousel auto-advance (during hold)
                if mode_carousel_active and now - mode_carousel_last_advance >= CAROUSEL_INTERVAL:
                    mode_carousel_idx = (mode_carousel_idx + 1) % len(MODE_KEYS)
                    mode_carousel_last_advance = now
                    self.screen.show_style_carousel(
                        MODE_NAMES, MODE_DESCS, mode_carousel_idx)
                    print(f"\r\n[Mode: {MODE_NAMES[mode_carousel_idx]}]\r\n",
                          end='', flush=True)

                event = inp.poll()
                if event is None:
                    continue

                # --- Mode carousel (hold to enter, click to confirm) ---
                if event == HOLD and not style_browsing and not mode_carousel_active:
                    mode_carousel_active = True
                    cur_idx = MODE_KEYS.index(mode)
                    mode_carousel_idx = (cur_idx + 1) % len(MODE_KEYS)
                    mode_carousel_last_advance = now
                    self.screen.show_style_carousel(
                        MODE_NAMES, MODE_DESCS, mode_carousel_idx, first_frame=True)
                    print(f"\r\n[Mode: {MODE_NAMES[mode_carousel_idx]}]\r\n",
                          end='', flush=True)
                    continue

                if event == QUIT:
                    print("\r\nQuitting...\r\n", end='')
                    break

                # --- Mode carousel selection ---
                if mode_carousel_active:
                    if event == CLICK:
                        selected = MODE_KEYS[mode_carousel_idx]
                        mode_carousel_active = False
                        mode, last_advance, slideshow_paused = self._switch_mode(
                            mode, selected, now, slideshow_paused)
                        print(f"\r\n[Mode: {MODE_NAMES[mode_carousel_idx]}]\r\n",
                              end='', flush=True)
                    elif event == DOUBLE_CLICK:
                        mode_carousel_active = False
                        print("\r\n[Mode cancelled]\r\n", end='', flush=True)
                        self._switch_mode(mode, mode, now, slideshow_paused)
                    continue

                # --- Style browsing ---
                if style_browsing:
                    if event == CLICK:
                        self.style = get_style(names[style_browse_idx])
                        style_browsing = False
                        print(f"\r\n[Style: {self.style.name}]\r\n", end='', flush=True)
                        self.screen.show_capture_mode()
                    elif event == DOUBLE_CLICK:
                        self.style = get_style(style_before_browse)
                        style_browsing = False
                        print("\r\n[Style cancelled]\r\n", end='', flush=True)
                        self.screen.show_capture_mode()
                    continue

                # --- Mode-specific actions ---
                if event == CLICK:
                    if mode == MODE_CAPTURE:
                        print("\r\n[Capture]\r\n", end='', flush=True)
                        self._run_with_bridge(web_bridge,
                                              lambda: self.dream_and_display())
                    elif mode == MODE_GALLERY and self.gallery.images:
                        self.gallery.next(self.display)
                    elif mode == MODE_SLIDESHOW and self.gallery.images:
                        slideshow_paused = not slideshow_paused
                        if slideshow_paused:
                            self.screen.show_overlay("Paused")
                        else:
                            last_advance = now
                            self.gallery.show_current(self.display)

                elif event == DOUBLE_CLICK:
                    if mode == MODE_CAPTURE:
                        style_browsing = True
                        style_before_browse = self.style.name
                        style_browse_idx = names.index(self.style.name)
                        style_browse_last_advance = now
                        print("\r\n[Style browse]\r\n", end='', flush=True)
                        self.screen.show_style_carousel(
                            names, prompts, style_browse_idx, first_frame=True)
                    elif mode == MODE_GALLERY and self.gallery.images:
                        self.gallery.prev(self.display)

                elif event == KEY_MODE:
                    cur_idx = MODE_KEYS.index(mode)
                    selected = MODE_KEYS[(cur_idx + 1) % len(MODE_KEYS)]
                    mode, last_advance, slideshow_paused = self._switch_mode(
                        mode, selected, now, slideshow_paused)
                    print(f"\r\n[{mode.title()}]\r\n", end='', flush=True)

                elif event == KEY_STYLE:
                    idx = names.index(self.style.name)
                    self.style = get_style(names[(idx + 1) % len(names)])
                    print(f"\rStyle: {self.style.name}\r\n"
                          f"\r  {self.style.prompt[:50]}...\r\n", end='', flush=True)

                elif event == KEY_CLEAR:
                    self.display.clear()
                    mode = MODE_CAPTURE
                    style_browsing = False
                    self.screen.show_capture_mode()

                elif event == KEY_RESET:
                    self.display.reset()
                    mode = MODE_CAPTURE
                    style_browsing = False
                    self.screen.show_capture_mode()

                elif event == WEB_SET_STYLE:
                    self.style = get_style(inp.web_payload)
                    print(f"\r[Web: style -> {self.style.name}]\r\n",
                          end='', flush=True)

                elif event == WEB_UPLOAD:
                    if mode == MODE_CAPTURE:
                        print("\r[Web: upload dream]\r\n", end='', flush=True)
                        self._run_with_bridge(web_bridge,
                                              lambda: self.dream_and_display_image(
                                                  inp.web_payload))

    @staticmethod
    def _run_with_bridge(bridge, fn):
        """Run fn(), updating bridge status if bridge is provided."""
        if bridge:
            from dreamcam.web.bridge import CameraStatus
            bridge.set_status(CameraStatus.DREAMING)
        try:
            fn()
            if bridge:
                bridge.set_status(CameraStatus.DONE)
        except Exception as e:
            print(f"\rError: {e}\r\n", end='', flush=True)
            if bridge:
                bridge.set_status(CameraStatus.ERROR, str(e))

    def _switch_mode(self, current: str, selected: str,
                     now: float, slideshow_paused: bool):
        """Switch to a new mode. Returns (mode, last_advance, slideshow_paused)."""
        if selected == MODE_CAPTURE:
            if self.last_image:
                self.display.show_image(self.last_image, mode=MODE_GC16)
            else:
                self.screen.show_capture_mode()
            return MODE_CAPTURE, now, False

        # Gallery or slideshow — need images
        if current in (MODE_GALLERY, MODE_SLIDESHOW) and self.gallery.images:
            # Already have images loaded, just switch behavior
            self.gallery.show_current(self.display)
            return selected, now, False

        # Entering gallery/slideshow from capture
        images = self.gallery.load()
        if not images:
            print("\rNo dreams saved\r\n", end='', flush=True)
            self.screen.show_capture_mode()
            return MODE_CAPTURE, now, False

        if selected == MODE_GALLERY:
            self.screen.show_gallery_mode(len(images))
        else:
            self.screen.show_slideshow_mode(len(images))
        self.gallery.show_current(self.display)
        return selected, now, False
