"""DisplayProxy -- wraps any Display to capture snapshots for web preview."""

from __future__ import annotations

import io
import threading

from PIL import Image

from dreamcam.display import MODE_GC16, MODE_INIT


class DisplayProxy:
    """Wraps a real Display, intercepting calls to maintain a JPEG snapshot.

    Satisfies the Display protocol so DreamCamera can't tell the difference.
    The web server reads ``snapshot`` from its own thread — all shared state
    is protected by a lock.
    """

    def __init__(self, inner):
        self._inner = inner
        self.width = inner.width
        self.height = inner.height

        self._lock = threading.Lock()
        self._framebuffer = Image.new('L', (self.width, self.height), 255)
        self._snapshot_bytes: bytes = b''
        self._version: int = 0
        self._encode_snapshot()  # initial blank frame

    # -- Display protocol methods (delegated + snapshot update) --

    def show_image(self, image, mode=MODE_GC16):
        self._inner.show_image(image, mode)
        if isinstance(image, str):
            img = Image.open(image)
        elif isinstance(image, bytes):
            img = Image.open(io.BytesIO(image))
        else:
            img = image
        img = img.convert('L').resize(
            (self.width, self.height), Image.Resampling.LANCZOS)
        self._update_snapshot(img)

    def display(self, image_data, x=0, y=0, w=None, h=None, mode=MODE_GC16):
        self._inner.display(image_data, x, y, w, h, mode)
        w = w or self.width
        h = h or self.height
        region = Image.frombytes('L', (w, h), image_data)
        with self._lock:
            self._framebuffer.paste(region, (x, y))
            self._encode_snapshot()

    def clear(self, mode=MODE_INIT):
        self._inner.clear(mode)
        with self._lock:
            self._framebuffer = Image.new('L', (self.width, self.height), 255)
            self._encode_snapshot()

    def reset(self):
        self._inner.reset()
        with self._lock:
            self._framebuffer = Image.new('L', (self.width, self.height), 255)
            self._encode_snapshot()

    def close(self):
        self._inner.close()

    # -- Snapshot access (called from web server thread) --

    @property
    def snapshot(self) -> tuple[bytes, int]:
        """Returns (jpeg_bytes, version). Thread-safe."""
        with self._lock:
            return self._snapshot_bytes, self._version

    def _update_snapshot(self, img: Image.Image):
        with self._lock:
            self._framebuffer = img
            self._encode_snapshot()

    def _encode_snapshot(self):
        """Encode framebuffer to JPEG. Must be called with lock held."""
        buf = io.BytesIO()
        self._framebuffer.save(buf, format='JPEG', quality=70)
        self._snapshot_bytes = buf.getvalue()
        self._version += 1
