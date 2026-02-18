"""Tests for the style registry."""

from dreamcam.styles import (
    ART, ENV, FRAME, TEXT, STYLES, Style,
    get_style, style_names, style_prompts, all_style_names_set,
    DEFAULT_STYLE, IMAGE_CATEGORIES,
)


def test_all_styles_have_required_fields():
    for s in STYLES:
        assert s.name, "Style must have a name"
        assert s.category, "Style must have a category"
        assert s.prompt, "Style must have a prompt"


def test_categories_are_valid():
    valid = {ART, FRAME, ENV, TEXT}
    for s in STYLES:
        assert s.category in valid, f"{s.name} has invalid category {s.category}"


def test_no_duplicate_names():
    names = [s.name for s in STYLES]
    assert len(names) == len(set(names)), "Duplicate style names found"


def test_get_style():
    s = get_style('clay')
    assert s.name == 'clay'
    assert s.category == ART


def test_get_style_missing():
    try:
        get_style('nonexistent')
        assert False, "Should raise KeyError"
    except KeyError:
        pass


def test_style_names_matches_styles():
    assert style_names() == [s.name for s in STYLES]


def test_style_prompts_matches_styles():
    assert style_prompts() == [s.prompt for s in STYLES]


def test_default_style_exists():
    s = get_style(DEFAULT_STYLE)
    assert s is not None


def test_is_text_mode():
    assert get_style('poem').is_text_mode
    assert get_style('haiku').is_text_mode
    assert not get_style('clay').is_text_mode
    assert not get_style('jungle').is_text_mode


def test_is_art_style():
    assert get_style('clay').is_art_style
    assert get_style('wanted').is_art_style      # FRAME is treated as art
    assert not get_style('jungle').is_art_style   # ENV
    assert not get_style('poem').is_art_style     # TEXT


def test_is_image_mode():
    assert get_style('clay').is_image_mode
    assert get_style('jungle').is_image_mode
    assert not get_style('poem').is_image_mode


def test_all_style_names_set():
    names_set = all_style_names_set()
    assert 'clay' in names_set
    assert 'poem' in names_set
    assert len(names_set) == len(STYLES)


def test_style_is_frozen():
    s = get_style('clay')
    try:
        s.name = 'something'
        assert False, "Style should be frozen"
    except AttributeError:
        pass
