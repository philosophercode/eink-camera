"""Tests for the AI transformer."""

from unittest.mock import MagicMock, patch

from PIL import Image

from dreamcam.styles import ART, ENV, TEXT, Style
from dreamcam.transform import Transformer, _image_to_bytes


def test_image_to_bytes():
    img = Image.new('RGB', (10, 10), (255, 0, 0))
    data = _image_to_bytes(img)
    assert isinstance(data, bytes)
    assert len(data) > 0
    # Should be valid JPEG
    assert data[:2] == b'\xff\xd8'


def test_transformer_no_api_key():
    t = Transformer(api_key=None)
    assert not t.available


def test_transformer_build_art_prompt():
    t = Transformer(api_key=None)
    style = Style('test', ART, "pencil sketch style")
    prompt = t._build_image_prompt(style)
    assert "Transform this photo into" in prompt
    assert "pencil sketch style" in prompt


def test_transformer_build_env_prompt():
    t = Transformer(api_key=None)
    style = Style('test', ENV, "tropical jungle")
    prompt = t._build_image_prompt(style)
    assert "place the person into a new environment" in prompt
    assert "tropical jungle" in prompt


def test_generate_text_no_client():
    t = Transformer(api_key=None)
    style = Style('test', TEXT, "Write a haiku")
    img = Image.new('RGB', (10, 10))
    result = t.generate_text(img, style)
    assert result == "AI not available"


def test_dream_no_client():
    t = Transformer(api_key=None)
    style = Style('test', ART, "pencil sketch")
    img = Image.new('RGB', (10, 10))
    try:
        t.dream(img, style)
        assert False, "Should raise RuntimeError"
    except RuntimeError as e:
        assert "not available" in str(e)


def test_describe_person_no_client():
    t = Transformer(api_key=None)
    result = t.describe_person(Image.new('RGB', (10, 10)))
    assert result == "a person"


def test_model_names_configurable():
    t = Transformer(api_key=None, image_model='custom-image', text_model='custom-text')
    assert t.image_model == 'custom-image'
    assert t.text_model == 'custom-text'
