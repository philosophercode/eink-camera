"""Tests for gallery image management."""

import os

from PIL import Image

from dreamcam.display.sim import SimDisplay
from dreamcam.gallery import Gallery


def _create_images(directory, names):
    """Helper to create test JPEG files."""
    for name in names:
        path = os.path.join(directory, name)
        Image.new('RGB', (10, 10), (128, 128, 128)).save(path)


def test_load_empty_dir(tmp_path):
    g = Gallery(str(tmp_path))
    images = g.load()
    assert images == []


def test_load_none_dir():
    g = Gallery(None)
    images = g.load()
    assert images == []


def test_load_filters_originals(tmp_path):
    d = str(tmp_path)
    _create_images(d, [
        "2024-01-01_original.jpg",
        "2024-01-01_clay.jpg",
        "2024-01-02_original.jpg",
        "2024-01-02_pencil.jpg",
    ])
    g = Gallery(d)
    images = g.load()
    assert len(images) == 2
    assert all('_original.' not in os.path.basename(f) for f in images)


def test_load_newest_first(tmp_path):
    d = str(tmp_path)
    _create_images(d, ["aaa_clay.jpg", "zzz_clay.jpg"])
    g = Gallery(d)
    images = g.load()
    # Reversed sorted order = newest first
    assert os.path.basename(images[0]) == "zzz_clay.jpg"


def test_next_wraps(tmp_path):
    d = str(tmp_path)
    _create_images(d, ["a_clay.jpg", "b_clay.jpg", "c_clay.jpg"])
    display = SimDisplay(width=10, height=10)

    g = Gallery(d)
    g.load()
    assert g.index == 0

    g.next(display)
    assert g.index == 1

    g.next(display)
    assert g.index == 2

    g.next(display)
    assert g.index == 0  # Wrapped


def test_prev_wraps(tmp_path):
    d = str(tmp_path)
    _create_images(d, ["a_clay.jpg", "b_clay.jpg"])
    display = SimDisplay(width=10, height=10)

    g = Gallery(d)
    g.load()
    assert g.index == 0

    g.prev(display)
    assert g.index == 1  # Wrapped to end


def test_show_current_empty():
    display = SimDisplay(width=10, height=10)
    g = Gallery(None)
    assert g.show_current(display) is False
