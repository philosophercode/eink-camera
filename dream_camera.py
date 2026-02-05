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

# Load .env file automatically
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass  # dotenv not installed, use environment variables directly

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


# Environment backgrounds - photorealistic, keeps the person the same
DREAM_STYLES = {
    'jungle': "dense tropical rainforest with lush green foliage, exotic plants, hanging vines, dappled sunlight through the canopy",
    'underwater': "deep ocean scene with blue water, coral reefs, tropical fish swimming around, light rays from above, bubbles",
    'city': "Times Square New York City at night with bright neon signs, yellow taxis, crowds of people, urban energy",
    'space': "floating in outer space with Earth visible below, stars and galaxies in background, astronaut vibes",
    'beach': "beautiful tropical beach at sunset, palm trees, golden sand, turquoise water, orange and pink sky",
    'mountain': "top of a snowy mountain peak, dramatic clouds below, bright blue sky, epic alpine vista",
    'mars': "surface of Mars with red rocky terrain, dusty atmosphere, distant mountains, alien landscape",
    'tokyo': "neon-lit Tokyo street at night, Japanese signs, rain-slicked streets, cyberpunk atmosphere",
    'safari': "African savanna at golden hour, acacia trees, distant elephants, dramatic sky, wild adventure",
    'castle': "inside a grand medieval castle, stone walls, torches, red banners, dramatic lighting",
}

DEFAULT_STYLE = 'jungle'


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

    def describe_person(self, image):
        """Use Gemini to describe the person in the image."""
        if not self.client:
            return "a person"

        # Convert PIL image to bytes
        buf = io.BytesIO()
        image.save(buf, format='JPEG')
        image_bytes = buf.getvalue()

        prompt = """Describe the person in this photo in detail for image generation.
        Include: their apparent age, gender, ethnicity, hair (color, style, length),
        facial features, expression, what they're wearing, their pose/posture.
        Be specific and detailed. Keep it to 2-3 sentences.
        Only describe the PERSON, not the background."""

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
            return "a person"

    def dream_image(self, image, quiet=False):
        """
        Place the person from the photo into a new environment.

        Returns a new PIL Image with the person in the new background.
        """
        if not quiet:
            print(f"  Teleporting to '{self.style}'...\r")

        # Get detailed description of the person
        person_desc = self.describe_person(image)
        if not quiet:
            print(f"  Person: {person_desc}\r")

        background = DREAM_STYLES[self.style]

        # Try to generate new image with Gemini image generation
        if self.client:
            try:
                prompt = f"""Photorealistic image of {person_desc}

The person is standing/positioned in this environment: {background}

IMPORTANT: Keep the person looking EXACTLY as described - same face, same clothes,
same pose. Only change the background/environment. Make it look like a real photograph,
not artistic or stylized. Professional photography quality."""

                response = self.client.models.generate_content(
                    model='nano-banana-pro-preview',
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
                if not quiet:
                    print(f"  Image generation error: {e}\r")

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

    def make_side_by_side(self, original, dreamed):
        """Create a side-by-side comparison image."""
        # Each image gets half the width
        half_w = self.width // 2
        h = self.height

        # Resize both images to fit
        orig_resized = original.convert('L').resize((half_w, h), Image.Resampling.LANCZOS)
        dream_resized = dreamed.convert('L').resize((half_w, h), Image.Resampling.LANCZOS)

        # Create combined image
        combined = Image.new('L', (self.width, h), 255)
        combined.paste(orig_resized, (0, 0))
        combined.paste(dream_resized, (half_w, 0))

        # Add divider line
        from PIL import ImageDraw
        draw = ImageDraw.Draw(combined)
        draw.line([(half_w, 0), (half_w, h)], fill=0, width=3)

        return combined

    def dream_and_display(self, side_by_side=False):
        """Capture, dream, and display."""
        print("Capturing...\r")
        photo = self.capture_photo()

        print("Processing with AI...\r")
        start = time.time()
        dreamed = self.dream_image(photo)
        print(f"  Dream time: {time.time() - start:.1f}s\r")

        print("Displaying...\r")
        if side_by_side:
            combined = self.make_side_by_side(photo, dreamed)
            self.display.show_image(combined, mode=MODE_GC16)
        else:
            self.display.show_image(dreamed, mode=MODE_GC16)
        print("Done!\r")

    def stream_dreams(self):
        """Continuous dream streaming."""
        print("Streaming dreams (press any key to stop)...\r")
        frame = 0
        start = time.time()

        while True:
            # Check for keypress
            if self._key_pressed():
                break

            photo = self.capture_photo()
            dreamed = self.dream_image(photo, quiet=True)
            self.display.show_image(dreamed, mode=MODE_A2)

            frame += 1
            elapsed = time.time() - start
            # Clear line and print status
            print(f"\r\033[KFrame {frame} ({frame/elapsed:.2f} fps)   ", end='', flush=True)

        print(f"\r\n\033[KStreamed {frame} dreams\r")

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
        print("  3 - Side-by-side (original + dream)")
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
                        self.dream_and_display(side_by_side=False)
                        print("\rReady (press 1 to dream)")
                    elif key == '3':
                        print("\r")
                        self.dream_and_display(side_by_side=True)
                        print("\rReady (press 3 for side-by-side)")
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
