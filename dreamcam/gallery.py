"""Gallery image loader for dream camera."""

from __future__ import annotations

import glob as _glob
import os

from dreamcam.display import MODE_GC16, MODE_INIT

# Full refresh every N gallery frames to prevent ghosting
GALLERY_REFRESH_INTERVAL = 6


class Gallery:
    """Manages browsing of saved dream images."""

    def __init__(self, dreams_dir: str | None):
        self.dreams_dir = dreams_dir
        self.images: list[str] = []
        self.index: int = 0
        self._frame_count: int = 0

    def load(self) -> list[str]:
        """Load dream images (excluding originals), newest first."""
        if not self.dreams_dir or not os.path.isdir(self.dreams_dir):
            self.images = []
            return self.images

        files = sorted(_glob.glob(os.path.join(self.dreams_dir, '*.jpg')))
        self.images = [f for f in files if '_original.' not in os.path.basename(f)]
        self.images.reverse()
        self.index = 0
        return self.images

    def show_current(self, display) -> bool:
        """Display image at current index. Returns False if empty/error."""
        if not self.images:
            return False
        return self._show(display, self.images[self.index])

    def next(self, display) -> bool:
        """Advance to next image and display it."""
        if not self.images:
            return False
        self.index = (self.index + 1) % len(self.images)
        return self._show(display, self.images[self.index])

    def prev(self, display) -> bool:
        """Go to previous image and display it."""
        if not self.images:
            return False
        self.index = (self.index - 1) % len(self.images)
        return self._show(display, self.images[self.index])

    def _show(self, display, path: str) -> bool:
        """Display a single image with periodic full refresh."""
        name = os.path.basename(path)
        total = len(self.images)
        print(f"\r  {self.index + 1}/{total}: {name}\r\n", end='', flush=True)
        try:
            if self._frame_count % GALLERY_REFRESH_INTERVAL == 0:
                display.clear(MODE_INIT)
            self._frame_count += 1
            display.show_image(path, mode=MODE_GC16)
            return True
        except Exception:
            print(f"\r  (skipping corrupt file)\r\n", end='', flush=True)
            return False
