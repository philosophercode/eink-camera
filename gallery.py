#!/usr/bin/env python3
"""Gallery image loader for dream camera."""

import os
import glob as _glob

from eink import MODE_GC16


def load_dream_images(dreams_dir):
    """Load dream images (excluding originals), newest first."""
    if not dreams_dir or not os.path.isdir(dreams_dir):
        return []
    files = sorted(_glob.glob(os.path.join(dreams_dir, '*.jpg')))
    images = [f for f in files if '_original.' not in os.path.basename(f)]
    images.reverse()
    return images


def show_gallery_image(display, images, idx):
    """Display image at index. Returns False if corrupt."""
    name = os.path.basename(images[idx])
    total = len(images)
    print(f"\r  {idx+1}/{total}: {name}\r\n", end='', flush=True)
    try:
        display.show_image(images[idx], mode=MODE_GC16)
        return True
    except Exception:
        print(f"\r  (skipping corrupt file)\r\n", end='', flush=True)
        return False
