# Architecture Refactor Plan

## The Problem

`dream_camera.py` is a 1030-line god class doing 5 unrelated jobs:
- AI transformation (Gemini API, prompt engineering)
- Input handling (230-line keyboard+GPIO state machine)
- Image capture (libcamera subprocess)
- Gallery/slideshow state management
- UI orchestration (spinner, threading)

Styles are hardcoded as a Python dict. Adding a new style category (say, "filters" or "frame overlays") means editing the class itself. The button state machine is interleaved with business logic, making both hard to follow.

Meanwhile, `eink.py`, `ui.py`, and `gallery.py` are already clean and focused — they show what the right granularity looks like.

## Proposed Structure

```
eink-camera/
├── eink.py            # Display driver         (KEEP — already clean)
├── ui.py              # Screen renderer         (KEEP — already clean)
├── gallery.py         # Gallery loader          (KEEP — already clean)
├── styles.py          # NEW: Style registry + categories
├── transform.py       # NEW: AI pipeline (Gemini client + prompts)
├── input.py           # NEW: Input manager (keyboard + GPIO state machine)
├── app.py             # NEW: Thin orchestrator (replaces DreamCamera)
├── dream_camera.py    # SLIM DOWN: Entry point only (argparse + bootstrap)
```

7 files, each with one job. No file over ~300 lines.

## What Changes

### 1. `styles.py` — Style Registry (~80 lines)

Styles become data with explicit categorization:

```python
# Style categories
ART = 'art'        # Transform the whole image style
ENV = 'env'        # Change the background/environment
TEXT = 'text'      # Generate text about the photo
FRAME = 'frame'    # Creative framing (wanted poster, trading card, etc.)

@dataclass
class Style:
    name: str
    category: str       # ART, ENV, TEXT, FRAME
    prompt: str
    description: str    # Short human-readable description for carousel

# Registry — a flat list, easily extended
STYLES: list[Style] = [
    Style('clay', ART, "transform into claymation...", "Claymation style"),
    Style('pencil', ART, "detailed pencil sketch...", "Pencil sketch"),
    # ...
    Style('wanted', FRAME, "old west wanted poster...", "Wanted poster"),
    Style('poem', TEXT, "Write a short poem...", "Poetry"),
    Style('jungle', ENV, "dense tropical rainforest...", "Jungle"),
]

# Lookup helpers
def get_style(name: str) -> Style: ...
def style_names() -> list[str]: ...
def is_text_mode(name: str) -> bool: ...
def is_art_style(name: str) -> bool: ...
```

**Why this matters for extensibility:**
- Adding a new category (e.g., FILTER for PIL-based transforms, or COMPOSITE for multi-image) is one new constant + styles that use it
- Adding a new style is one line — no class modifications
- The style carousel just iterates the list — category-aware filtering is trivial
- Could later load from a YAML/JSON file without changing any consumer code

### 2. `transform.py` — AI Transformer (~120 lines)

All Gemini API interaction in one place:

```python
class Transformer:
    def __init__(self, api_key: str | None = None):
        # Initialize Gemini client (with graceful fallback)

    def dream(self, image: Image, style: Style) -> Image:
        # Build prompt based on style.category
        # Call Gemini image generation
        # Return transformed image

    def generate_text(self, image: Image, style: Style) -> str:
        # Call Gemini text generation
        # Return text response

    def describe_person(self, image: Image) -> str:
        # Person description for environment styles
```

**Extension points:**
- Swap `Transformer` for a different AI backend (DALL-E, Stable Diffusion, local model)
- Add a `FallbackTransformer` that uses PIL filters when offline
- Model names become constructor params, not hardcoded strings

### 3. `input.py` — Input Manager (~150 lines)

Encapsulates the entire button state machine + keyboard into a clean event interface:

```python
# Events
CLICK = 'click'
DOUBLE_CLICK = 'double_click'
HOLD = 'hold'

class InputManager:
    def __init__(self, gpio_pin: int | None = None):
        # Set up keyboard (if TTY) and GPIO (if pin provided)

    def poll(self) -> str | None:
        # Returns event name or None
        # Handles: debounce, hold detection, click counting, timeout

    def close(self):
        # Restore terminal, close GPIO
```

The 230-line state machine from `run()` becomes a self-contained class.
The main loop becomes:

```python
while True:
    event = input_mgr.poll()
    if event == CLICK:
        self.on_click()
    elif event == DOUBLE_CLICK:
        self.on_double_click()
    elif event == HOLD:
        self.on_hold()
```

**Extension point:** Adding a new input source (network trigger, remote API, IR remote)
is just a new class with the same `poll() -> event` interface.

### 4. `app.py` — Application Controller (~250 lines)

The thin orchestrator. Wires components together, manages mode state:

```python
class DreamCamera:
    def __init__(self, device, api_key, save_dir, gpio_pin):
        self.display = EInkDisplay(device)
        self.screen = ScreenRenderer(self.display)
        self.transformer = Transformer(api_key)
        self.input = InputManager(gpio_pin)
        self.style = get_style(DEFAULT_STYLE)
        # ...

    def capture(self) -> Image:
        # libcamera-still (10 lines, not worth its own module)

    def dream_and_display(self):
        # Capture → show preview → spinner thread → transform → display
        # Unified pipeline for both text and image modes

    def on_click(self):
        # Mode-dependent action dispatch

    def on_double_click(self):
        # Mode-dependent action dispatch

    def on_hold(self):
        # Enter mode carousel

    def run(self):
        # Main loop — trivially simple with InputManager
```

### 5. `dream_camera.py` — Entry Point (~50 lines)

Just argparse and bootstrap. Imports `app.DreamCamera` and calls `run()`.

## What Stays the Same

- **`eink.py`** — Already clean. Single responsibility (SCSI driver). No changes.
- **`ui.py`** — Already clean. Renders screens. No changes.
- **`gallery.py`** — Already clean. Loads/displays gallery images. No changes.
- **The C code** — Left alone. It's a separate implementation for a different use case.

## Key Design Decisions

### Why not YAML/JSON for styles?
A Python file is simpler, importable, type-checkable, and doesn't need a parser dependency. The style "registry" pattern means consumers don't care where styles come from — switching to file-based loading later is a one-line change in `styles.py`.

### Why not an abstract base class for Transformer?
YAGNI. There's one AI backend (Gemini). If a second appears, extract the interface then. The separation into its own module is enough to make swapping easy.

### Why InputManager returns events instead of using callbacks?
Polling fits the existing architecture (single-threaded main loop with sleep). Callbacks would require threading or an event loop — more complexity for no benefit on a Raspberry Pi driving an e-ink screen.

### Why keep capture in app.py instead of its own module?
It's 10 lines — a subprocess call and an Image.open. A separate module would be pure ceremony. If capture gets more complex (bracketing, HDR, video), then extract it.

## Extensibility Summary

| Want to add...              | Where                           | How                                  |
|-----------------------------|---------------------------------|--------------------------------------|
| New art style               | `styles.py`                     | One `Style(...)` line                |
| New style category          | `styles.py`                     | New constant + styles using it       |
| Different AI backend        | `transform.py`                  | New class, same interface            |
| New input source            | `input.py`                      | New class with `poll()` method       |
| New UI screen               | `ui.py`                         | New method on ScreenRenderer         |
| New operational mode        | `app.py`                        | New `on_click` dispatch branch       |
| PIL-based offline filters   | `transform.py`                  | `FallbackTransformer` class          |
| Style loading from file     | `styles.py`                     | Change registry init, nothing else   |

## Migration

This is a refactor, not a rewrite. The actual logic stays identical — it's just moved to the right home. Each piece can be extracted and tested independently:

1. Extract `styles.py` (pure data, no dependencies)
2. Extract `transform.py` (depends on genai only)
3. Extract `input.py` (depends on lgpio/termios only)
4. Rewrite `app.py` using the new modules
5. Slim `dream_camera.py` to entry point

No behavior changes. Same UX. Same button interactions. Same display output.
