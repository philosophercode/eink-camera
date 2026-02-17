#!/usr/bin/env python3
"""Gallery image loader for dream camera."""

import os
import glob as _glob

from eink import MODE_GC16, MODE_INIT

# Full refresh every N gallery frames to prevent ghosting
GALLERY_REFRESH_INTERVAL = 6
_gallery_frame_count = 0


def load_dream_images(dreams_dir):
    """Load dream images (excluding originals), newest first."""
    if not dreams_dir or not os.path.isdir(dreams_dir):
        return []
    files = sorted(_glob.glob(os.path.join(dreams_dir, '*.jpg')))
    images = [f for f in files if '_original.' not in os.path.basename(f)]
    images.reverse()
    return images


def show_gallery_image(display, images, idx):
    """Display image at index. Full clear every N frames to prevent ghosting."""
    global _gallery_frame_count
    name = os.path.basename(images[idx])
    total = len(images)
    print(f"\r  {idx+1}/{total}: {name}\r\n", end='', flush=True)
    try:
        # Periodic full refresh to clear ghosting artifacts
        if _gallery_frame_count % GALLERY_REFRESH_INTERVAL == 0:
            display.clear(MODE_INIT)
        _gallery_frame_count += 1
        display.show_image(images[idx], mode=MODE_GC16)
        return True
    except Exception:
        print(f"\r  (skipping corrupt file)\r\n", end='', flush=True)
        return False
