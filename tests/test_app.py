"""Tests for the app orchestrator."""

import os
from unittest.mock import patch, MagicMock

from PIL import Image

from dreamcam.app import DreamCamera, MODE_CAPTURE, MODE_GALLERY, MODE_SLIDESHOW
from dreamcam.display.sim import SimDisplay
from dreamcam.styles import get_style


def test_dream_camera_init(sim_display, mock_transformer, save_dir):
    cam = DreamCamera(display=sim_display, transformer=mock_transformer,
                      save_dir=save_dir)
    assert cam.style.name == 'clay'
    assert cam.capture_count == 0
    assert cam.last_image is None


def test_dream_camera_creates_save_dir(sim_display, mock_transformer, tmp_path):
    d = str(tmp_path / "new_dir")
    cam = DreamCamera(display=sim_display, transformer=mock_transformer,
                      save_dir=d)
    assert os.path.isdir(d)


def test_process_image_mode(sim_display, mock_transformer, save_dir):
    cam = DreamCamera(display=sim_display, transformer=mock_transformer,
                      save_dir=save_dir)
    photo = Image.new('RGB', (100, 100), (128, 128, 128))

    cam._process_image_mode(photo)

    mock_transformer.dream.assert_called_once()
    assert cam.last_image is not None
    # Should have saved files
    files = os.listdir(save_dir)
    assert len(files) == 2  # original + dreamed


def test_process_text_mode(sim_display, mock_transformer, save_dir):
    cam = DreamCamera(display=sim_display, transformer=mock_transformer,
                      save_dir=save_dir)
    cam.style = get_style('poem')
    photo = Image.new('RGB', (100, 100), (128, 128, 128))

    cam._process_text_mode(photo)

    mock_transformer.generate_text.assert_called_once()
    assert cam.last_image is None  # Text modes don't set last_image
    # Should have saved original + text file
    files = os.listdir(save_dir)
    assert any(f.endswith('.txt') for f in files)
    assert any(f.endswith('.jpg') for f in files)


def test_spinner_frame(sim_display, mock_transformer):
    cam = DreamCamera(display=sim_display, transformer=mock_transformer)
    frame = cam._spinner_frame(0)
    assert frame.size == (120, 120)
    assert frame.mode == 'L'


def test_switch_mode_to_capture(sim_display, mock_transformer):
    cam = DreamCamera(display=sim_display, transformer=mock_transformer)
    mode, _, _ = cam._switch_mode(MODE_GALLERY, MODE_CAPTURE, 0, False)
    assert mode == MODE_CAPTURE


def test_switch_mode_to_gallery_no_images(sim_display, mock_transformer):
    cam = DreamCamera(display=sim_display, transformer=mock_transformer,
                      save_dir="/nonexistent")
    mode, _, _ = cam._switch_mode(MODE_CAPTURE, MODE_GALLERY, 0, False)
    # No images -> falls back to capture
    assert mode == MODE_CAPTURE


def test_save_images_no_dir(sim_display, mock_transformer):
    cam = DreamCamera(display=sim_display, transformer=mock_transformer,
                      save_dir=None)
    # Should not raise
    cam._save_images(Image.new('RGB', (10, 10)), Image.new('RGB', (10, 10)))


def test_save_text_no_dir(sim_display, mock_transformer):
    cam = DreamCamera(display=sim_display, transformer=mock_transformer,
                      save_dir=None)
    # Should not raise
    cam._save_text(Image.new('RGB', (10, 10)), "hello")
