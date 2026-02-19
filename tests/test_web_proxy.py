"""Tests for DisplayProxy."""

import io
import threading

from PIL import Image

from dreamcam.display.sim import SimDisplay
from dreamcam.web.proxy import DisplayProxy


class TestDisplayProxy:

    def _make_proxy(self, width=200, height=150):
        inner = SimDisplay(width=width, height=height)
        proxy = DisplayProxy(inner)
        return proxy, inner

    def test_delegates_show_image(self):
        proxy, inner = self._make_proxy()
        img = Image.new('L', (200, 150), 100)
        proxy.show_image(img)
        # Inner display should have been called
        assert inner.frame_count >= 1

    def test_snapshot_updated_after_show_image(self):
        proxy, _ = self._make_proxy()
        _, v0 = proxy.snapshot
        img = Image.new('L', (200, 150), 50)
        proxy.show_image(img)
        jpeg_bytes, v1 = proxy.snapshot
        assert v1 > v0
        assert len(jpeg_bytes) > 0
        # Verify it's valid JPEG
        decoded = Image.open(io.BytesIO(jpeg_bytes))
        assert decoded.size == (200, 150)

    def test_snapshot_updated_after_partial_display(self):
        proxy, _ = self._make_proxy()
        _, v0 = proxy.snapshot
        region = Image.new('L', (50, 50), 0)
        proxy.display(region.tobytes(), x=10, y=10, w=50, h=50)
        _, v1 = proxy.snapshot
        assert v1 > v0

    def test_clear_resets_snapshot(self):
        proxy, _ = self._make_proxy()
        img = Image.new('L', (200, 150), 0)
        proxy.show_image(img)
        _, v1 = proxy.snapshot
        proxy.clear()
        jpeg_bytes, v2 = proxy.snapshot
        assert v2 > v1
        # Should be white after clear
        decoded = Image.open(io.BytesIO(jpeg_bytes))
        pixels = list(decoded.getdata())
        assert all(p == 255 for p in pixels)

    def test_reset_clears_snapshot(self):
        proxy, _ = self._make_proxy()
        img = Image.new('L', (200, 150), 0)
        proxy.show_image(img)
        _, v1 = proxy.snapshot
        proxy.reset()
        _, v2 = proxy.snapshot
        assert v2 > v1

    def test_version_increments_monotonically(self):
        proxy, _ = self._make_proxy()
        versions = []
        _, v = proxy.snapshot
        versions.append(v)
        for i in range(5):
            proxy.show_image(Image.new('L', (200, 150), i * 50))
            _, v = proxy.snapshot
            versions.append(v)
        assert versions == sorted(versions)
        assert len(set(versions)) == len(versions)  # all unique

    def test_width_height_pass_through(self):
        proxy, inner = self._make_proxy(800, 600)
        assert proxy.width == 800
        assert proxy.height == 600

    def test_show_image_from_path(self, tmp_path):
        proxy, _ = self._make_proxy()
        img_path = tmp_path / "test.jpg"
        Image.new('L', (200, 150), 80).save(str(img_path))
        proxy.show_image(str(img_path))
        jpeg_bytes, _ = proxy.snapshot
        assert len(jpeg_bytes) > 0

    def test_thread_safety(self):
        """Concurrent reads from web thread while main thread writes."""
        proxy, _ = self._make_proxy()
        errors = []

        def reader():
            for _ in range(50):
                try:
                    jpeg_bytes, version = proxy.snapshot
                    if jpeg_bytes:
                        Image.open(io.BytesIO(jpeg_bytes))
                except Exception as e:
                    errors.append(e)

        def writer():
            for i in range(50):
                proxy.show_image(Image.new('L', (200, 150), i % 256))

        t_read = threading.Thread(target=reader)
        t_write = threading.Thread(target=writer)
        t_read.start()
        t_write.start()
        t_read.join()
        t_write.join()
        assert errors == []
