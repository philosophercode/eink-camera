"""Shared test fixtures."""

from __future__ import annotations

import os
import tempfile
from unittest.mock import MagicMock

import pytest
from PIL import Image

from dreamcam.display.sim import SimDisplay
from dreamcam.styles import get_style


@pytest.fixture
def sim_display():
    """SimDisplay with no file output (fast, in-memory only)."""
    return SimDisplay(width=800, height=600)


@pytest.fixture
def sim_display_with_output(tmp_path):
    """SimDisplay that writes frames to a temp directory."""
    return SimDisplay(width=800, height=600, output_dir=str(tmp_path))


@pytest.fixture
def test_image():
    """A small test image."""
    return Image.new('RGB', (200, 150), color=(128, 128, 128))


@pytest.fixture
def mock_transformer():
    """Mock transformer that returns predictable results."""
    t = MagicMock()
    t.available = True
    t.dream.return_value = Image.new('L', (200, 150), color=100)
    t.generate_text.return_value = "A test poem about the photo."
    t.describe_person.return_value = "a person wearing a hat"
    return t


@pytest.fixture
def save_dir(tmp_path):
    """Temporary directory for saving images."""
    d = tmp_path / "dreams"
    d.mkdir()
    return str(d)
