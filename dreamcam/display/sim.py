"""
Display simulator for development without hardware.

Renders to an in-memory PIL framebuffer. Optionally saves each frame
to disk and/or shows a live tkinter preview window.

Usage:
    from dreamcam.display import create_display

    display = create_display('sim', output_dir='./frames')
    display.show_image('photo.jpg')
    display.framebuffer.show()  # Open in system viewer
"""

import io
import os

from PIL import Image

from dreamcam.display import MODE_GC16, MODE_INIT


class SimDisplay:
    """E-ink display simulator backed by a PIL Image framebuffer."""

    def __init__(self, width=1872, height=1404, output_dir=None):
        self.width = width
        self.height = height
        self.output_dir = output_dir
        self.framebuffer = Image.new('L', (width, height), 255)
        self.frame_count = 0
        self.log: list[dict] = []  # Operation log for testing

        if output_dir:
            os.makedirs(output_dir, exist_ok=True)

        print(f"SimDisplay: {width}x{height}"
              + (f", saving to {output_dir}" if output_dir else ""))

    def show_image(self, image, mode=MODE_GC16):
        """Display a PIL Image, file path, or bytes."""
        if isinstance(image, str):
            img = Image.open(image)
        elif isinstance(image, bytes):
            img = Image.open(io.BytesIO(image))
        else:
            img = image

        img = img.convert('L').resize((self.width, self.height),
                                      Image.Resampling.LANCZOS)
        self.framebuffer = img
        self._record('show_image', mode=mode)

    def display(self, image_data, x=0, y=0, w=None, h=None, mode=MODE_GC16):
        """Write raw grayscale bytes to a region of the framebuffer."""
        w = w or self.width
        h = h or self.height
        region = Image.frombytes('L', (w, h), image_data)
        self.framebuffer.paste(region, (x, y))
        self._record('display', x=x, y=y, w=w, h=h, mode=mode)

    def clear(self, mode=MODE_INIT):
        """Clear framebuffer to white."""
        self.framebuffer = Image.new('L', (self.width, self.height), 255)
        self._record('clear', mode=mode)

    def reset(self):
        """No-op for simulator."""
        self.clear()
        self._record('reset')

    def close(self):
        """No-op for simulator."""
        self._record('close')

    def _record(self, operation, **kwargs):
        """Log operation and optionally save frame."""
        self.log.append({'op': operation, 'frame': self.frame_count, **kwargs})
        if self.output_dir:
            path = os.path.join(self.output_dir, f'frame_{self.frame_count:04d}.png')
            self.framebuffer.save(path)
        self.frame_count += 1

    def __enter__(self):
        return self

    def __exit__(self, *args):
        self.close()
