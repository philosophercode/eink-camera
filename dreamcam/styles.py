"""
Style registry for dream camera transformations.

Each style has a category that determines how it's processed:
  - ART:   Transform the entire image style (clay, pencil, comic, etc.)
  - FRAME: Creative framing with text/layout (wanted poster, trading card)
  - ENV:   Change the background/environment (jungle, space, tokyo)
  - TEXT:  Generate text about the photo (poem, haiku, roast)

Adding a style: append a Style(...) to STYLES below.
Adding a category: define a new constant + styles that use it, then handle
the category in transform.py's prompt builder.
"""

from __future__ import annotations

from dataclasses import dataclass

# Categories
ART = 'art'
FRAME = 'frame'
ENV = 'env'
TEXT = 'text'

# Categories that produce images (vs text)
IMAGE_CATEGORIES = {ART, FRAME, ENV}


@dataclass(frozen=True)
class Style:
    name: str
    category: str
    prompt: str

    @property
    def is_text_mode(self) -> bool:
        return self.category == TEXT

    @property
    def is_image_mode(self) -> bool:
        return self.category in IMAGE_CATEGORIES

    @property
    def is_art_style(self) -> bool:
        """Art styles transform the whole image (vs env styles that change background)."""
        return self.category in (ART, FRAME)


# --- Style definitions ---
# Order here = order in the carousel.

STYLES: list[Style] = [
    # Art styles
    Style('clay', ART, "transform into a claymation character like Wallace and Gromit, smooth clay texture, stop-motion animation style, handcrafted look"),
    Style('pencil', ART, "detailed pencil sketch drawing, fine graphite lines, subtle shading, artist sketchbook style, hand-drawn"),
    Style('sharpie', ART, "bold black sharpie marker drawing, thick confident lines, high contrast, minimal detail, street art style"),
    Style('lineart', ART, "clean line art illustration, precise outlines, no shading, coloring book style, vector-like"),
    Style('charcoal', ART, "expressive charcoal drawing, smudged edges, dramatic shadows, fine art style, textured paper"),
    Style('watercolor', ART, "soft watercolor painting, flowing colors bleeding together, wet on wet technique, artistic"),
    Style('comic', ART, "comic book style, bold outlines, halftone dots, pop art colors, superhero illustration"),
    Style('pixel', ART, "retro pixel art, 16-bit video game style, blocky pixels, nostalgic gaming aesthetic"),
    Style('sculpture', ART, "classical marble sculpture, ancient Greek/Roman statue, carved stone, museum quality"),
    Style('woodcut', ART, "traditional woodblock print, bold black lines, vintage illustration style, old book aesthetic"),

    # Creative framing
    Style('wanted', FRAME, "old west wanted poster on aged yellowed parchment, big bold text WANTED DEAD OR ALIVE at top, reward amount at bottom, rough sketch portrait style"),
    Style('card', FRAME, "collectible trading card with ornate portrait frame, character stats and attributes along the bottom, name plate, holographic border, game card style"),
    Style('newspaper', FRAME, "old-timey newspaper front page, large dramatic headline, grainy halftone photo, columns of text, vintage newsprint, The Daily Chronicle masthead"),
    Style('poster', FRAME, "dramatic cinematic movie poster, epic lighting, movie title at bottom in bold typography, credits text, theatrical one-sheet style"),
    Style('album', FRAME, "music album cover, artistic composition, band name text at top, album title, vinyl record aesthetic, iconic cover art style"),

    # Fun transforms
    Style('lego', ART, "Lego minifigure version, plastic brick style, yellow skin, blocky proportions, Lego set box art aesthetic"),
    Style('stained', ART, "stained glass window design, lead lines between colored glass segments, cathedral window style, jewel tones, backlit glow"),
    Style('tattoo', ART, "traditional tattoo flash sheet, bold black outlines, classic American traditional tattoo style, banner with text, old school ink"),

    # Time/era transforms
    Style('victorian', ART, "daguerreotype portrait, sepia toned, formal Victorian-era pose, ornate oval frame, 1860s photography style, slight vignette"),
    Style('renaissance', ART, "classical Renaissance oil painting portrait, ornate gilded frame, Rembrandt lighting, rich dark background, Old Masters style"),
    Style('future', ART, "cyberpunk sci-fi portrait, neon accents, holographic elements, futuristic HUD overlay, digital glitch effects, year 2084 aesthetic"),

    # Text modes
    Style('describe', TEXT, "Describe what you see in this photo in vivid, evocative detail. Write 2-3 sentences that paint a picture with words."),
    Style('poem', TEXT, "Write a short poem (4-8 lines) inspired by what you see in this photo. Be creative and evocative."),
    Style('haiku', TEXT, "Write a haiku (three lines: 5 syllables, 7 syllables, 5 syllables) inspired by this photo."),
    Style('roast', TEXT, "Write a funny, playful roast of what you see in this photo. Keep it lighthearted and good-natured. 1-2 sentences."),
    Style('fortune', TEXT, "Look at this photo and write a mysterious, cryptic fortune cookie prediction inspired by what you see. One sentence only."),
    Style('story', TEXT, "Write a 3-sentence flash fiction story inspired by this photo. Make it intriguing and complete."),

    # Environments
    Style('jungle', ENV, "dense tropical rainforest with lush green foliage, exotic plants, hanging vines, dappled sunlight through the canopy"),
    Style('underwater', ENV, "deep ocean scene with blue water, coral reefs, tropical fish swimming around, light rays from above, bubbles"),
    Style('city', ENV, "Times Square New York City at night with bright neon signs, yellow taxis, crowds of people, urban energy"),
    Style('space', ENV, "floating in outer space with Earth visible below, stars and galaxies in background, astronaut vibes"),
    Style('beach', ENV, "beautiful tropical beach at sunset, palm trees, golden sand, turquoise water, orange and pink sky"),
    Style('mountain', ENV, "top of a snowy mountain peak, dramatic clouds below, bright blue sky, epic alpine vista"),
    Style('mars', ENV, "surface of Mars with red rocky terrain, dusty atmosphere, distant mountains, alien landscape"),
    Style('tokyo', ENV, "neon-lit Tokyo street at night, Japanese signs, rain-slicked streets, cyberpunk atmosphere"),
    Style('safari', ENV, "African savanna at golden hour, acacia trees, distant elephants, dramatic sky, wild adventure"),
    Style('castle', ENV, "inside a grand medieval castle, stone walls, torches, red banners, dramatic lighting"),
]

DEFAULT_STYLE = 'clay'

# --- Lookup helpers ---

_BY_NAME: dict[str, Style] = {s.name: s for s in STYLES}


def get_style(name: str) -> Style:
    """Get a style by name. Raises KeyError if not found."""
    return _BY_NAME[name]


def style_names() -> list[str]:
    """All style names in carousel order."""
    return [s.name for s in STYLES]


def style_prompts() -> list[str]:
    """All style prompts in carousel order (for carousel display)."""
    return [s.prompt for s in STYLES]


def all_style_names_set() -> set[str]:
    """Set of all valid style names (for argparse choices)."""
    return set(_BY_NAME.keys())
