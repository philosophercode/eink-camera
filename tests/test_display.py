"""Tests for display backends."""

import os

from PIL import Image

from dreamcam.display import Display, MODE_A2, MODE_GC16, MODE_INIT, create_display
from dreamcam.display.sim import SimDisplay


def test_sim_display_is_display_protocol():
    """SimDisplay satisfies the Display protocol."""
    d = SimDisplay()
    assert isinstance(d, Display)


def test_sim_display_dimensions():
    d = SimDisplay(width=100, height=50)
    assert d.width == 100
    assert d.height == 50


def test_sim_display_default_dimensions():
    d = SimDisplay()
    assert d.width == 1872
    assert d.height == 1404


def test_sim_clear():
    d = SimDisplay(width=10, height=10)
    d.clear()
    # Framebuffer should be all white (255)
    pixels = list(d.framebuffer.getdata())
    assert all(p == 255 for p in pixels)


def test_sim_show_image_pil():
    d = SimDisplay(width=100, height=50)
    img = Image.new('L', (200, 100), color=0)
    d.show_image(img)
    # Framebuffer should be resized to display dimensions
    assert d.framebuffer.size == (100, 50)


def test_sim_partial_display():
    d = SimDisplay(width=100, height=100)
    d.clear()
    # Write a 10x10 black patch at (5, 5)
    patch = bytes([0] * 100)
    d.display(patch, x=5, y=5, w=10, h=10, mode=MODE_A2)
    # Check the patch area is dark
    assert d.framebuffer.getpixel((5, 5)) == 0
    assert d.framebuffer.getpixel((14, 14)) == 0
    # Check outside is still white
    assert d.framebuffer.getpixel((0, 0)) == 255


def test_sim_log():
    d = SimDisplay(width=10, height=10)
    d.clear()
    d.show_image(Image.new('L', (10, 10), 128))
    assert len(d.log) == 2
    assert d.log[0]['op'] == 'clear'
    assert d.log[1]['op'] == 'show_image'


def test_sim_frame_output(tmp_path):
    d = SimDisplay(width=10, height=10, output_dir=str(tmp_path))
    d.clear()
    d.show_image(Image.new('L', (10, 10), 128))
    files = sorted(os.listdir(tmp_path))
    assert files == ['frame_0000.png', 'frame_0001.png']


def test_sim_context_manager():
    with SimDisplay(width=10, height=10) as d:
        d.clear()
    assert d.log[-1]['op'] == 'close'


def test_sim_reset():
    d = SimDisplay(width=10, height=10)
    d.show_image(Image.new('L', (10, 10), 0))
    d.reset()
    # After reset, framebuffer should be white
    pixels = list(d.framebuffer.getdata())
    assert all(p == 255 for p in pixels)


def test_create_display_sim():
    d = create_display('sim', width=100, height=50)
    assert isinstance(d, SimDisplay)
    assert d.width == 100


def test_create_display_invalid():
    try:
        create_display('quantum')
        assert False, "Should raise ValueError"
    except ValueError:
        pass


def test_show_image_from_file(tmp_path):
    # Save a test image to disk
    path = str(tmp_path / "test.jpg")
    Image.new('RGB', (50, 50), (128, 128, 128)).save(path)

    d = SimDisplay(width=100, height=100)
    d.show_image(path)
    assert d.framebuffer.size == (100, 100)
