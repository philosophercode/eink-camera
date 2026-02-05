#!/usr/bin/env python3
"""
AI Dream Camera - Captures photos and reimagines them with AI.

Takes a photo, sends it to Gemini for creative interpretation,
generates a new "hallucinated" version, and displays on e-ink.

Usage:
    export GOOGLE_API_KEY="your-api-key"
    sudo python3 dream_camera.py /dev/sg0

Controls:
    1 - Capture and dream
    2 - Stream dreams (continuous)
    s - Change style/prompt
    c - Clear display
    q - Quit
"""

import os
import sys
import io
import time
import subprocess
import select
import termios
import tty
from PIL import Image

# Import our e-ink driver
from eink import EInkDisplay, MODE_GC16, MODE_A2

# Google AI imports (new google-genai package)
try:
    from google import genai
    from google.genai import types
    HAS_GENAI = True
except ImportError:
    HAS_GENAI = False
    print("Warning: google-genai not installed")
    print("Install with: pip install google-genai pillow")


# Dream styles/prompts
DREAM_STYLES = {
    'surreal': "Reimagine this scene in a surrealist style like Salvador Dali - melting objects, impossible geometry, dreamlike atmosphere",
    'noir': "Transform this into a dramatic film noir scene - high contrast, deep shadows, mysterious mood",
    'anime': "Reimagine this as a Studio Ghibli anime scene - soft colors, whimsical details, magical atmosphere",
    'sketch': "Transform this into an elegant pencil sketch - fine lines, cross-hatching, artistic shading",
    'cyberpunk': "Reimagine this as a cyberpunk scene - neon lights, rain, futuristic technology, Blade Runner aesthetic",
    'vintage': "Transform this into a vintage 1920s photograph - sepia tones, film grain, art deco elements",
    'abstract': "Reimagine this as an abstract expressionist painting - bold shapes, emotional colors, gestural marks",
    'nightmare': "Transform this into a dark, unsettling scene - distorted proportions, eerie lighting, subtle wrongness",
    'dreamy': "Make this more dreamlike and ethereal - soft focus, floating elements, pastel colors, magical realism",
    'minimal': "Simplify this into a minimal Japanese ink painting - few brushstrokes, lots of white space, zen aesthetic",
}

DEFAULT_STYLE = 'dreamy'


class DreamCamera:
    """AI-powered camera that reimagines what it sees."""

    def __init__(self, device='/dev/sg0', api_key=None):
        self.display = EInkDisplay(device)
        self.style = DEFAULT_STYLE
        self.width = self.display.width
        self.height = self.display.height

        # Initialize Gemini
        self.client = None
        if HAS_GENAI:
            api_key = api_key or os.environ.get('GOOGLE_API_KEY')
            if api_key:
                self.client = genai.Client(api_key=api_key)
                print("Gemini API connected!")
            else:
                print("Warning: No GOOGLE_API_KEY set")
        else:
            print("Warning: google-genai not installed")

    def capture_photo(self):
        """Capture a photo using libcamera."""
        tmp_path = '/tmp/capture.jpg'
        cmd = [
            'libcamera-still',
            '-o', tmp_path,
            '--width', str(self.width),
            '--height', str(self.height),
            '-t', '1',
            '--nopreview'
        ]
        subprocess.run(cmd, capture_output=True)
        return Image.open(tmp_path)

    def describe_image(self, image):
        """Use Gemini to describe the image creatively."""
        if not self.client:
            return "A mysterious scene awaits interpretation..."

        # Convert PIL image to bytes
        buf = io.BytesIO()
        image.save(buf, format='JPEG')
        image_bytes = buf.getvalue()

        prompt = f"""Look at this image and create a vivid, creative description
        that could be used to generate a reimagined version.

        Style requested: {DREAM_STYLES[self.style]}

        Describe what you see, then describe how it would look transformed
        in this style. Be specific about colors, mood, composition, and details.
        Keep it to 2-3 sentences focused on visual elements."""

        try:
            response = self.client.models.generate_content(
                model='gemini-2.0-flash',
                contents=[
                    types.Content(
                        role='user',
                        parts=[
                            types.Part.from_text(text=prompt),
                            types.Part.from_bytes(data=image_bytes, mime_type='image/jpeg'),
                        ]
                    )
                ]
            )
            return response.text
        except Exception as e:
            print(f"  Gemini error: {e}")
            return "A scene transformed by imagination..."

    def dream_image(self, image):
        """
        Transform an image through AI "dreaming".

        Returns a new PIL Image that's a reimagined version.
        """
        print(f"  Dreaming in '{self.style}' style...")

        # Get creative description from Gemini
        description = self.describe_image(image)
        print(f"  Vision: {description[:100]}...")

        # Try to generate new image with Gemini image generation
        if self.client:
            try:
                prompt = f"{DREAM_STYLES[self.style]}. Based on this scene: {description}"
                response = self.client.models.generate_content(
                    model='gemini-2.0-flash-exp-image-generation',
                    contents=prompt,
                    config=types.GenerateContentConfig(
                        response_modalities=['image', 'text'],
                    )
                )
                # Extract image from response
                for part in response.candidates[0].content.parts:
                    if hasattr(part, 'inline_data') and part.inline_data:
                        img_bytes = part.inline_data.data
                        return Image.open(io.BytesIO(img_bytes))
            except Exception as e:
                print(f"  Image generation error: {e}")

        # Fallback: apply filters to original
        return self._fallback_dream(image, description)

    def _fallback_dream(self, image, description):
        """
        Fallback when Imagen isn't available.
        Apply dramatic artistic transformations.
        """
        from PIL import ImageFilter, ImageEnhance, ImageOps
        import random

        img = image.convert('L')  # Grayscale first

        # Apply dramatic style-based filters
        if self.style == 'surreal':
            # Solarize + emboss for weird dreamlike effect
            img = ImageOps.solarize(img, threshold=128)
            img = img.filter(ImageFilter.EMBOSS)
            img = ImageOps.autocontrast(img)

        elif self.style == 'nightmare':
            # Invert + find edges + high contrast
            img = ImageOps.invert(img)
            img = img.filter(ImageFilter.FIND_EDGES)
            enhancer = ImageEnhance.Contrast(img)
            img = enhancer.enhance(3.0)

        elif self.style == 'dreamy':
            # Heavy blur + posterize for soft dream effect
            img = img.filter(ImageFilter.GaussianBlur(5))
            img = ImageOps.posterize(img, 3)
            enhancer = ImageEnhance.Contrast(img)
            img = enhancer.enhance(1.5)

        elif self.style == 'noir':
            # High contrast + edge detection
            enhancer = ImageEnhance.Contrast(img)
            img = enhancer.enhance(3.0)
            img = ImageOps.posterize(img, 2)

        elif self.style == 'sketch':
            # Edge detection + invert for pencil sketch look
            img = img.filter(ImageFilter.FIND_EDGES)
            img = ImageOps.invert(img)
            enhancer = ImageEnhance.Contrast(img)
            img = enhancer.enhance(2.0)

        elif self.style == 'vintage':
            # Posterize + slight blur for old photo look
            img = ImageOps.posterize(img, 4)
            img = img.filter(ImageFilter.SMOOTH)

        elif self.style == 'minimal':
            # Strong contour for line art
            img = img.filter(ImageFilter.CONTOUR)
            img = ImageOps.invert(img)
            img = ImageOps.autocontrast(img)

        elif self.style == 'cyberpunk':
            # Emboss + solarize for digital glitch feel
            img = img.filter(ImageFilter.EMBOSS)
            img = ImageOps.solarize(img, threshold=100)
            enhancer = ImageEnhance.Contrast(img)
            img = enhancer.enhance(2.0)

        elif self.style == 'anime':
            # Posterize heavily for cel-shaded look
            img = ImageOps.posterize(img, 2)
            img = img.filter(ImageFilter.EDGE_ENHANCE_MORE)

        elif self.style == 'abstract':
            # Multiple filters for chaotic effect
            img = img.filter(ImageFilter.EMBOSS)
            img = ImageOps.posterize(img, 2)
            img = img.filter(ImageFilter.FIND_EDGES)
            img = ImageOps.invert(img)

        return img

    def dream_and_display(self):
        """Capture, dream, and display."""
        print("Capturing...")
        photo = self.capture_photo()

        print("Processing with AI...")
        start = time.time()
        dreamed = self.dream_image(photo)
        print(f"  Dream time: {time.time() - start:.1f}s")

        print("Displaying...")
        self.display.show_image(dreamed, mode=MODE_GC16)
        print("Done!")

    def stream_dreams(self):
        """Continuous dream streaming."""
        print("Streaming dreams (press any key to stop)...")
        frame = 0
        start = time.time()

        while True:
            # Check for keypress
            if self._key_pressed():
                break

            photo = self.capture_photo()
            dreamed = self.dream_image(photo)
            self.display.show_image(dreamed, mode=MODE_A2)

            frame += 1
            elapsed = time.time() - start
            print(f"\rFrame {frame} ({frame/elapsed:.2f} fps)", end='', flush=True)

        print(f"\nStreamed {frame} dreams")

    def _key_pressed(self):
        """Check if a key was pressed (non-blocking)."""
        return select.select([sys.stdin], [], [], 0)[0]

    def cycle_style(self):
        """Cycle through dream styles."""
        styles = list(DREAM_STYLES.keys())
        idx = styles.index(self.style)
        self.style = styles[(idx + 1) % len(styles)]
        print(f"Style: {self.style}")
        print(f"  {DREAM_STYLES[self.style][:60]}...")

    def run(self):
        """Main interactive loop."""
        print("\n=== AI Dream Camera ===")
        print(f"Display: {self.width}x{self.height}")
        print(f"Style: {self.style}")
        print("\nControls:")
        print("  1 - Capture and dream")
        print("  2 - Stream dreams")
        print("  s - Change style")
        print("  c - Clear display")
        print("  q - Quit\n")

        # Set terminal to raw mode
        old_settings = termios.tcgetattr(sys.stdin)
        try:
            tty.setraw(sys.stdin.fileno())

            while True:
                if select.select([sys.stdin], [], [], 0.1)[0]:
                    key = sys.stdin.read(1)

                    if key == 'q':
                        print("\r\nQuitting...")
                        break
                    elif key == '1':
                        print("\r")
                        self.dream_and_display()
                        print("\rReady (press 1 to dream)")
                    elif key == '2':
                        print("\r")
                        self.stream_dreams()
                        print("\rReady")
                    elif key == 's':
                        print("\r")
                        self.cycle_style()
                    elif key == 'c':
                        print("\rClearing...")
                        self.display.clear()
                        print("\rReady")

        finally:
            termios.tcsetattr(sys.stdin, termios.TCSADRAIN, old_settings)
            self.display.close()


def main():
    if len(sys.argv) < 2:
        print("AI Dream Camera")
        print(f"Usage: sudo python3 {sys.argv[0]} /dev/sgX")
        print("\nRequires:")
        print("  pip install google-generativeai pillow")
        print("  export GOOGLE_API_KEY='your-key'")
        sys.exit(1)

    device = sys.argv[1]
    camera = DreamCamera(device)
    camera.run()


if __name__ == '__main__':
    main()
