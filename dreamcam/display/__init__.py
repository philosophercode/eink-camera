"""
Display abstraction for e-ink screens.

The Display protocol defines the interface. Concrete implementations:
  - USBDisplay: IT8951 over USB/SCSI (the default)
  - SimDisplay: PIL-based simulator for development without hardware

Usage:
    from dreamcam.display import create_display, MODE_GC16

    display = create_display('usb', device='/dev/sg0')
    display = create_display('sim', output_dir='./frames')
"""

from __future__ import annotations

from typing import Protocol, Union, runtime_checkable

from PIL import Image

# Display refresh modes (IT8951 standard, shared across all backends)
MODE_INIT = 0   # Full clear (slow, removes ghosting)
MODE_DU = 1     # Direct update (fast, 1-bit)
MODE_GC16 = 2   # 16-level grayscale (best quality)
MODE_A2 = 4     # Fast 2-level B&W (for video/animation)


@runtime_checkable
class Display(Protocol):
    """Interface for e-ink display backends."""

    width: int
    height: int

    def show_image(self, image: Union[Image.Image, str, bytes],
                   mode: int = MODE_GC16) -> None:
        """Display a PIL Image, file path, or raw bytes."""
        ...

    def display(self, image_data: bytes, x: int = 0, y: int = 0,
                w: int | None = None, h: int | None = None,
                mode: int = MODE_GC16) -> None:
        """Write raw grayscale bytes to a region of the display."""
        ...

    def clear(self, mode: int = MODE_INIT) -> None:
        """Clear display to white."""
        ...

    def reset(self) -> None:
        """Reset the display connection."""
        ...

    def close(self) -> None:
        """Release resources."""
        ...


def create_display(backend: str = 'usb', **kwargs) -> Display:
    """
    Factory for display backends.

    Args:
        backend: 'usb' for IT8951 over USB/SCSI, 'sim' for simulator
        **kwargs: Passed to the backend constructor.
            usb: device='/dev/sg0'
            sim: width=1872, height=1404, output_dir=None
    """
    if backend == 'usb':
        from dreamcam.display.usb import USBDisplay
        return USBDisplay(**kwargs)
    elif backend == 'sim':
        from dreamcam.display.sim import SimDisplay
        return SimDisplay(**kwargs)
    else:
        raise ValueError(f"Unknown display backend: {backend!r}")
