"""
AI image transformation using Google Gemini.

Handles all Gemini API interaction: image generation, text generation,
and person description for environment compositing.

The Transformer class is the only module that imports google-genai.
Swap it out for a different AI backend by matching the interface.
"""

from __future__ import annotations

import io
from typing import TYPE_CHECKING

from PIL import Image

from dreamcam.styles import Style

if TYPE_CHECKING:
    pass

# Lazy import — google-genai is loaded on first use, not at import time.
# This keeps the module importable in environments where genai or its
# transitive dependencies (cryptography, etc.) are broken or missing.
_genai = None
_types = None
_genai_loaded = False


def _load_genai():
    """Try to import google-genai. Safe to call multiple times."""
    global _genai, _types, _genai_loaded
    if _genai_loaded:
        return _genai is not None
    _genai_loaded = True
    try:
        from google import genai
        from google.genai import types
        _genai, _types = genai, types
        return True
    except BaseException:
        return False


# Default model names (can be overridden in constructor)
IMAGE_MODEL = 'nano-banana-pro-preview'
TEXT_MODEL = 'gemini-2.0-flash'


def _image_to_bytes(image: Image.Image) -> bytes:
    """Convert PIL Image to JPEG bytes."""
    buf = io.BytesIO()
    image.save(buf, format='JPEG')
    return buf.getvalue()


class Transformer:
    """Transforms photos using Gemini AI."""

    def __init__(self, api_key: str | None = None,
                 image_model: str = IMAGE_MODEL,
                 text_model: str = TEXT_MODEL):
        self.client = None
        self.image_model = image_model
        self.text_model = text_model

        if not _load_genai():
            print("Warning: google-genai not installed")
            return

        if not api_key:
            print("Warning: No API key provided")
            return

        self.client = _genai.Client(api_key=api_key)
        print("Gemini API connected!")

    @property
    def available(self) -> bool:
        return self.client is not None

    def dream(self, image: Image.Image, style: Style) -> Image.Image:
        """
        Transform a photo into the given style.

        Returns a new PIL Image.
        Raises RuntimeError if AI is not available.
        """
        if not self.client:
            raise RuntimeError("AI not available")

        image_bytes = _image_to_bytes(image)
        prompt = self._build_image_prompt(style)

        response = self.client.models.generate_content(
            model=self.image_model,
            contents=[
                _types.Content(
                    role='user',
                    parts=[
                        _types.Part.from_bytes(data=image_bytes, mime_type='image/jpeg'),
                        _types.Part.from_text(text=prompt),
                    ]
                )
            ],
            config=_types.GenerateContentConfig(
                response_modalities=['image', 'text'],
            )
        )

        for part in response.candidates[0].content.parts:
            if hasattr(part, 'inline_data') and part.inline_data:
                return Image.open(io.BytesIO(part.inline_data.data))

        raise RuntimeError("No image in API response")

    def generate_text(self, image: Image.Image, style: Style) -> str:
        """Generate text about a photo (for text modes like poem, haiku, roast)."""
        if not self.client:
            return "AI not available"

        image_bytes = _image_to_bytes(image)

        response = self.client.models.generate_content(
            model=self.text_model,
            contents=[
                _types.Content(
                    role='user',
                    parts=[
                        _types.Part.from_bytes(data=image_bytes, mime_type='image/jpeg'),
                        _types.Part.from_text(text=style.prompt),
                    ]
                )
            ]
        )
        return response.text.strip()

    def describe_person(self, image: Image.Image) -> str:
        """Describe the person in a photo (used for environment-style compositing)."""
        if not self.client:
            return "a person"

        image_bytes = _image_to_bytes(image)
        prompt = (
            "Describe the person in this photo in detail for image generation. "
            "Include: their apparent age, gender, ethnicity, hair (color, style, length), "
            "facial features, expression, what they're wearing, their pose/posture. "
            "Be specific and detailed. Keep it to 2-3 sentences. "
            "Only describe the PERSON, not the background."
        )

        try:
            response = self.client.models.generate_content(
                model=self.text_model,
                contents=[
                    _types.Content(
                        role='user',
                        parts=[
                            _types.Part.from_text(text=prompt),
                            _types.Part.from_bytes(data=image_bytes, mime_type='image/jpeg'),
                        ]
                    )
                ]
            )
            return response.text
        except Exception:
            return "a person"

    def _build_image_prompt(self, style: Style) -> str:
        """Build the generation prompt based on style category."""
        if style.is_art_style:
            return (
                f"Transform this photo into: {style.prompt}\n\n"
                "Keep the same composition, pose, and subject but completely "
                "change the artistic style. Make it look like an authentic "
                "piece in this style, not a filter."
            )
        else:
            # Environment style
            return (
                f"Take this photo and place the person into a new environment: "
                f"{style.prompt}\n\n"
                "Keep the person looking EXACTLY the same - same face, same clothes, "
                "same pose, same expression. Only change the background/environment "
                "around them. Make it look like a real photograph, photorealistic, "
                "professional photography quality. The person should look naturally "
                "composited into the new scene with proper lighting and shadows."
            )
