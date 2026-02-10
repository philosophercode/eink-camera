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
from eink import EInkDisplay, MODE_GC16, MODE_A2, MODE_INIT

# Google AI imports (new google-genai package)
try:
    from google import genai
    from google.genai import types
    HAS_GENAI = True
except ImportError:
    HAS_GENAI = False
    print("Warning: google-genai not installed")
    print("Install with: pip install google-genai pillow")


# Dream styles - environments and art styles
DREAM_STYLES = {
    # Environments - change the background
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
    # Art styles - transform the image style
    'clay': "transform into a claymation character like Wallace and Gromit, smooth clay texture, stop-motion animation style, handcrafted look",
    'pencil': "detailed pencil sketch drawing, fine graphite lines, subtle shading, artist sketchbook style, hand-drawn",
    'sharpie': "bold black sharpie marker drawing, thick confident lines, high contrast, minimal detail, street art style",
    'lineart': "clean line art illustration, precise outlines, no shading, coloring book style, vector-like",
    'charcoal': "expressive charcoal drawing, smudged edges, dramatic shadows, fine art style, textured paper",
    'watercolor': "soft watercolor painting, flowing colors bleeding together, wet on wet technique, artistic",
    'comic': "comic book style, bold outlines, halftone dots, pop art colors, superhero illustration",
    'pixel': "retro pixel art, 16-bit video game style, blocky pixels, nostalgic gaming aesthetic",
    'sculpture': "classical marble sculpture, ancient Greek/Roman statue, carved stone, museum quality",
    'woodcut': "traditional woodblock print, bold black lines, vintage illustration style, old book aesthetic",
}

DEFAULT_STYLE = 'jungle'


class DreamCamera:
    """AI-powered camera that reimagines what it sees."""

    def __init__(self, device='/dev/sg0', api_key=None, save_dir=None):
        self.display = EInkDisplay(device)
        self.style = DEFAULT_STYLE
        self.width = self.display.width
        self.height = self.display.height
        self.save_dir = save_dir
        self.last_image = None  # Store last displayed image
        self.capture_count = 0  # Track captures for auto-reset

        # Create save directory if specified
        if self.save_dir:
            os.makedirs(self.save_dir, exist_ok=True)
            print(f"Saving images to: {self.save_dir}")

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

    def save_images(self, original, dreamed):
        """Save original and dreamed images with timestamp."""
        if not self.save_dir:
            return None, None

        from datetime import datetime
        timestamp = datetime.now().strftime('%Y-%m-%d_%H-%M-%S')

        orig_path = os.path.join(self.save_dir, f"{timestamp}_original.jpg")
        dream_path = os.path.join(self.save_dir, f"{timestamp}_{self.style}.jpg")

        original.convert('RGB').save(orig_path, quality=95)
        dreamed.convert('RGB').save(dream_path, quality=95)

        print(f"\rSaved: {os.path.basename(orig_path)}\r\n", flush=True)
        print(f"\rSaved: {os.path.basename(dream_path)}\r\n", flush=True)
        return orig_path, dream_path

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

    # Art styles that transform the whole image (vs environment styles that change background)
    ART_STYLES = {'clay', 'pencil', 'sharpie', 'lineart', 'charcoal', 'watercolor', 'comic', 'pixel', 'sculpture', 'woodcut'}

    def dream_image(self, image, quiet=False):
        """
        Transform the photo - either new environment or art style.

        Returns a new PIL Image.
        """
        if not quiet:
            print(f"  Dreaming '{self.style}'...\r")

        style_desc = DREAM_STYLES[self.style]
        is_art_style = self.style in self.ART_STYLES

        # Try to generate new image with Gemini image generation
        if self.client:
            try:
                # Convert image to bytes
                buf = io.BytesIO()
                image.save(buf, format='JPEG')
                image_bytes = buf.getvalue()

                if is_art_style:
                    # Art style - transform the entire image
                    prompt = f"""Transform this photo into: {style_desc}

Keep the same composition, pose, and subject but completely change the artistic style.
Make it look like an authentic piece in this style, not a filter."""
                else:
                    # Environment style - change the background
                    prompt = f"""Take this photo and place the person into a new environment: {style_desc}

Keep the person looking EXACTLY the same - same face, same clothes, same pose, same expression.
Only change the background/environment around them. Make it look like a real photograph,
photorealistic, professional photography quality. The person should look naturally composited
into the new scene with proper lighting and shadows."""

                response = self.client.models.generate_content(
                    model='nano-banana-pro-preview',
                    contents=[
                        types.Content(
                            role='user',
                            parts=[
                                types.Part.from_bytes(data=image_bytes, mime_type='image/jpeg'),
                                types.Part.from_text(text=prompt),
                            ]
                        )
                    ],
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

    # Spinner size constant
    SPINNER_SIZE = 120

    def get_spinner_region(self, frame):
        """Create a spinning circle indicator."""
        from PIL import ImageDraw
        import math
        region = Image.new('L', (self.SPINNER_SIZE, self.SPINNER_SIZE), 255)
        draw = ImageDraw.Draw(region)

        cx, cy = self.SPINNER_SIZE // 2, self.SPINNER_SIZE // 2
        radius = 40

        # Draw circle outline
        draw.ellipse([cx - radius, cy - radius, cx + radius, cy + radius],
                     outline=180, width=6)

        # Draw spinning arc (darker)
        arc_length = 90  # degrees
        start_angle = (frame * 45) % 360
        end_angle = start_angle + arc_length
        draw.arc([cx - radius, cy - radius, cx + radius, cy + radius],
                 start=start_angle, end=end_angle, fill=0, width=8)

        return region

    def dream_and_display(self, side_by_side=False):
        """Capture, dream, and display with loading animation."""
        import threading

        print("\rCapturing...\r\n", flush=True)
        photo = self.capture_photo()

        # Show photo immediately
        photo_gray = photo.convert('L').resize((self.width, self.height))
        self.display.show_image(photo_gray, mode=MODE_A2)

        # Spinner position (top right corner with margin)
        spinner_x = self.width - self.SPINNER_SIZE - 30
        spinner_y = 30

        # Start AI processing in background thread
        result = [None]
        error = [None]

        def process():
            try:
                result[0] = self.dream_image(photo, quiet=True)
            except Exception as e:
                error[0] = e

        thread = threading.Thread(target=process)
        thread.start()

        # Animate spinner while waiting (partial refresh only)
        print("\rProcessing with AI...\r\n", flush=True)
        start = time.time()
        frame = 0

        while thread.is_alive():
            # Update just the spinner region (partial refresh)
            spinner = self.get_spinner_region(frame)
            self.display.display(spinner.tobytes(), x=spinner_x, y=spinner_y,
                                w=self.SPINNER_SIZE, h=self.SPINNER_SIZE, mode=MODE_A2)
            frame += 1
            time.sleep(0.2)

        thread.join()
        print(f"\rDream time: {time.time() - start:.1f}s\r\n", flush=True)

        if error[0]:
            print(f"\rError: {error[0]}\r\n", flush=True)
            return

        dreamed = result[0]

        # Save images if save_dir is set
        self.save_images(photo, dreamed)

        # Show final result
        print("\rDisplaying...\r\n", flush=True)
        if side_by_side:
            final_image = self.make_side_by_side(photo, dreamed)
        else:
            final_image = dreamed.convert('L').resize((self.width, self.height), Image.Resampling.LANCZOS)

        self.display.show_image(final_image, mode=MODE_GC16)
        self.last_image = final_image  # Store for style banner restore
        self.capture_count += 1
        print("\rDone!\r\n", flush=True)

        # Auto-reset every 10 captures to prevent freezing
        if self.capture_count % 10 == 0:
            print("\r[Auto-reset to prevent freeze]\r\n", flush=True)
            self.display.reset()
            if self.last_image:
                self.display.show_image(self.last_image, mode=MODE_GC16)

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

    def show_style_banner(self):
        """Show current style as banner on display, then restore last image."""
        from PIL import ImageDraw, ImageFont

        # Create banner image
        img = Image.new('L', (self.width, self.height), 255)
        draw = ImageDraw.Draw(img)

        # Try to load fonts
        try:
            font_big = ImageFont.truetype("/usr/share/fonts/truetype/freefont/FreeSansBold.ttf", 120)
            font_small = ImageFont.truetype("/usr/share/fonts/truetype/freefont/FreeSans.ttf", 48)
        except:
            font_big = font_small = None

        # Style name
        style_name = self.style.upper()
        draw.text((self.width // 2, self.height // 2 - 50),
                  f"[ {style_name} ]", anchor="mm", font=font_big, fill=0)

        # Description
        desc = DREAM_STYLES[self.style][:60] + "..."
        draw.text((self.width // 2, self.height // 2 + 80),
                  desc, anchor="mm", font=font_small, fill=80)

        # Show banner with fast refresh
        self.display.show_image(img, mode=MODE_A2)

    def cycle_style(self, show_banner=False):
        """Cycle through dream styles."""
        styles = list(DREAM_STYLES.keys())
        idx = styles.index(self.style)
        self.style = styles[(idx + 1) % len(styles)]
        print(f"\rStyle: {self.style}\r\n\r  {DREAM_STYLES[self.style][:50]}...\r\n", flush=True)
        if show_banner:
            self.show_style_banner()

    def run(self, gpio_pin=None):
        """Main interactive loop with optional GPIO button support."""
        print("\n=== AI Dream Camera ===")
        print(f"Display: {self.width}x{self.height}")
        print(f"Style: {self.style}")
        print("\nControls:")
        print("  1 / short press  - Capture and dream")
        print("  s / hold 1.5s    - Enter style mode")
        print("      (press to cycle, double-click or wait to confirm)")
        print("  3 - Side-by-side")
        print("  2 - Stream")
        print("  c - Clear")
        print("  r - Reset display (if frozen)")
        print("  q - Quit")

        # Set up GPIO button if specified
        gpio_chip = None
        last_button_state = 1
        button_press_time = 0
        style_mode = False
        style_mode_start = 0
        last_style_press = 0
        if gpio_pin is not None:
            try:
                import lgpio
                try:
                    gpio_chip = lgpio.gpiochip_open(4)  # Pi 5
                except:
                    gpio_chip = lgpio.gpiochip_open(0)  # Older Pi
                lgpio.gpio_claim_input(gpio_chip, gpio_pin, lgpio.SET_PULL_UP)
                print(f"  Button on GPIO{gpio_pin} ready!")
            except Exception as e:
                print(f"  GPIO setup failed: {e}")
                gpio_chip = None

        print("")

        # Set terminal to raw mode
        old_settings = termios.tcgetattr(sys.stdin)
        try:
            tty.setraw(sys.stdin.fileno())

            while True:
                # Check keyboard
                if select.select([sys.stdin], [], [], 0.05)[0]:
                    key = sys.stdin.read(1)

                    if key == 'q':
                        print("\r\nQuitting...\r\n")
                        break
                    elif key == '1':
                        self.dream_and_display(side_by_side=False)
                    elif key == '3':
                        self.dream_and_display(side_by_side=True)
                    elif key == '2':
                        self.stream_dreams()
                    elif key == 's':
                        self.cycle_style()
                    elif key == 'c':
                        print("\r\nClearing...\r\n", flush=True)
                        self.display.clear()
                        print("\rDone!\r\n", flush=True)
                    elif key == 'r':
                        print("\r\nResetting display...\r\n", flush=True)
                        self.display.reset()
                        print("\rDone!\r\n", flush=True)

                # Check GPIO button with style mode
                if gpio_chip is not None:
                    import lgpio
                    state = lgpio.gpio_read(gpio_chip, gpio_pin)
                    now = time.time()

                    if not style_mode:
                        # Normal mode
                        if last_button_state == 1 and state == 0:
                            # Button pressed - start timing
                            button_press_time = now

                        elif last_button_state == 0 and state == 0:
                            # Button still held - check for long press
                            if now - button_press_time >= 1.5 and not style_mode:
                                # Enter style mode
                                style_mode = True
                                style_mode_start = now
                                last_style_press = now
                                print("\r\n[Style Mode]\r\n", flush=True)
                                self.show_style_banner()

                        elif last_button_state == 0 and state == 1:
                            # Button released - short press = capture
                            if now - button_press_time < 1.5:
                                print("\r\n[Capture]\r\n", flush=True)
                                self.dream_and_display(side_by_side=False)

                    else:
                        # Style mode - each press cycles, timeout or double-click exits
                        if last_button_state == 1 and state == 0:
                            # Button pressed in style mode
                            if now - last_style_press < 0.4:
                                # Double click - exit style mode
                                print("\r\n[Style confirmed]\r\n", flush=True)
                                style_mode = False
                                if self.last_image:
                                    self.display.show_image(self.last_image, mode=MODE_A2)
                            else:
                                # Single press - cycle style
                                self.cycle_style(show_banner=True)
                                last_style_press = now

                        # Timeout - exit style mode after 3 seconds of no input
                        if now - last_style_press > 3.0:
                            print("\r\n[Style confirmed]\r\n", flush=True)
                            style_mode = False
                            if self.last_image:
                                self.display.show_image(self.last_image, mode=MODE_A2)

                    last_button_state = state

        finally:
            termios.tcsetattr(sys.stdin, termios.TCSADRAIN, old_settings)
            if gpio_chip is not None:
                import lgpio
                lgpio.gpiochip_close(gpio_chip)
            self.display.close()


def run_button_mode(camera, gpio_pin=17, side_by_side=False):
    """Run in physical button mode - press button to capture and dream."""
    import lgpio

    print(f"\n=== BUTTON MODE ===")
    print(f"GPIO pin: {gpio_pin} (connect red wire)")
    print(f"Style: {camera.style}")
    print("Press the button to capture and dream!")
    print("Ctrl+C to quit\n")

    # Open GPIO chip (Pi 5 uses gpiochip4)
    try:
        chip = lgpio.gpiochip_open(4)  # Pi 5
    except:
        chip = lgpio.gpiochip_open(0)  # Older Pi

    # Set up pin as input with pull-up resistor
    lgpio.gpio_claim_input(chip, gpio_pin, lgpio.SET_PULL_UP)

    shot_count = 0
    last_state = 1  # Pull-up means high when not pressed

    try:
        while True:
            state = lgpio.gpio_read(chip, gpio_pin)

            # Button pressed (falling edge: was high, now low)
            if last_state == 1 and state == 0:
                shot_count += 1
                print(f"\n[Shot {shot_count}] Button pressed!")
                camera.dream_and_display(side_by_side=side_by_side)
                print("Ready for next shot...")

            last_state = state
            time.sleep(0.05)  # 50ms debounce

    except KeyboardInterrupt:
        print(f"\n\nExiting. Took {shot_count} dream shots.")
    finally:
        lgpio.gpiochip_close(chip)


def main():
    import argparse
    parser = argparse.ArgumentParser(description='AI Dream Camera')
    parser.add_argument('device', nargs='?', default='/dev/sg0', help='E-ink device path')
    parser.add_argument('--once', action='store_true', help='Take one dream photo and exit (no interactive mode)')
    parser.add_argument('--gpio', type=int, default=17, help='GPIO pin for button (default: 17)')
    parser.add_argument('--no-button', action='store_true', help='Disable physical button')
    parser.add_argument('--style', choices=list(DREAM_STYLES.keys()), default=DEFAULT_STYLE, help='Dream style/environment')
    parser.add_argument('--side-by-side', action='store_true', help='Show original and dream side by side')
    parser.add_argument('--save', metavar='DIR', default='~/dreams', help='Save images to directory (default: ~/dreams)')
    parser.add_argument('--no-save', action='store_true', help='Disable auto-saving images')
    args = parser.parse_args()

    # Expand ~ in save path (use actual user's home when running with sudo)
    if args.no_save:
        save_dir = None
    else:
        save_path = args.save
        if save_path.startswith('~') and os.environ.get('SUDO_USER'):
            # Running with sudo - use the original user's home
            import pwd
            real_home = pwd.getpwnam(os.environ['SUDO_USER']).pw_dir
            save_path = save_path.replace('~', real_home, 1)
        else:
            save_path = os.path.expanduser(save_path)
        save_dir = save_path

    camera = DreamCamera(args.device, save_dir=save_dir)
    camera.style = args.style

    if args.once:
        # Non-interactive mode - just take one photo and dream it
        print(f"Style: {camera.style}")
        camera.dream_and_display(side_by_side=args.side_by_side)
        camera.display.close()
    else:
        # Interactive mode - keyboard + button (button enabled by default)
        gpio_pin = None if args.no_button else args.gpio
        camera.run(gpio_pin=gpio_pin)


if __name__ == '__main__':
    main()
