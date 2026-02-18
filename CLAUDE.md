# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

E-ink camera for Raspberry Pi that captures photos and displays them on an IT8951 e-ink display via USB. The main feature is "dream mode" which uses Google's Gemini AI to reimagine captured photos in different art styles or environments before displaying them.

## Build & Run

### C application (standalone camera, no AI)
```bash
make                          # Build
sudo ./camera /dev/sda        # Run (requires root for SCSI device access)
```

### Python application (AI dream camera)
```bash
pip install -e ".[all]"           # Install package with all extras
export GOOGLE_API_KEY="..."       # Required for Gemini AI features
sudo dreamcam /dev/sg0            # Run via CLI entry point
sudo python -m dreamcam /dev/sg0  # Or run as module
sudo ./dream /dev/sg0             # Or via wrapper script
```

### Simulator mode (no hardware needed)
```bash
pip install -e "."                           # Base package only (just pillow)
python -m dreamcam --backend sim             # Run with simulated display
python -m dreamcam --sim-dir ./frames        # Save frames to disk
```

### Tests
```bash
pip install -e ".[dev]"     # Install with dev dependencies
pytest                      # Run all tests (no hardware needed)
pytest -v                   # Verbose output
```

## Architecture

### Package structure (`dreamcam/`)

```
dreamcam/
├── __init__.py        # Version
├── __main__.py        # CLI entry point (argparse + bootstrap)
├── app.py             # DreamCamera orchestrator — wires all components
├── styles.py          # Style registry with categories (ART, ENV, TEXT, FRAME)
├── transform.py       # Gemini AI client (image generation + text generation)
├── input.py           # Input manager (keyboard + GPIO state machine)
├── ui.py              # Screen renderer for e-ink UI screens
├── gallery.py         # Gallery browser for saved dream images
└── display/
    ├── __init__.py    # Display protocol + mode constants + factory
    ├── usb.py         # IT8951 USB/SCSI driver (production)
    └── sim.py         # PIL-based simulator (development + testing)
```

### Display Protocol (`dreamcam/display/`)
All display backends implement the `Display` protocol: `show_image()`, `display()` (partial), `clear()`, `reset()`, `close()`. Use `create_display('usb')` or `create_display('sim')` factory.

Display modes: `MODE_INIT` (0, full clear), `MODE_DU` (1, fast 1-bit), `MODE_GC16` (2, 16-level grayscale), `MODE_A2` (4, fast B&W for animation).

The USB driver (`usb.py`) sends SCSI vendor commands (0xfe prefix) via Linux SG_IO ioctl. Image data in chunks (max 60800 bytes). Big-endian coordinates, little-endian buffer address.

### Style System (`styles.py`)
Styles are `Style` dataclasses with `name`, `category`, and `prompt`. Categories:
- **ART**: Transform image style (clay, pencil, comic, etc.)
- **FRAME**: Creative framing (wanted poster, trading card, newspaper)
- **ENV**: Change background (jungle, space, tokyo)
- **TEXT**: Generate text about photo (poem, haiku, roast)

Add a style: one `Style(...)` line in `STYLES` list. Add a category: one constant + styles using it.

### Transformer (`transform.py`)
All Gemini API interaction. `Transformer.dream(image, style)` for images, `.generate_text(image, style)` for text modes. Lazy-loads google-genai (deferred import) so the package works without it installed.

### Input Manager (`input.py`)
Unified keyboard + GPIO with `poll() -> event` interface. Events: `CLICK`, `DOUBLE_CLICK`, `HOLD`, `QUIT`, `KEY_*`. Encapsulates button debounce, hold detection, click counting.

### App Orchestrator (`app.py`)
`DreamCamera` class wires display, transformer, input, UI, and gallery. Pipeline: capture via libcamera-still -> preview on e-ink -> spinner animation -> AI transform -> display result. Three operational modes: Capture, Gallery, Slideshow.

### GPIO Button Support
Physical button on GPIO17 (configurable) with pull-up resistor. Short press = capture, long hold (1.5s) = enter mode carousel, double-click = browse styles.

### Other Files
- `runner.py` — Animated sprite demo for testing e-ink refresh rates
- `example_simple.py` — Minimal usage examples (test pattern, capture, display)
- `dream` / `dcam` — Bash launcher scripts that activate the venv
- C files (`camera.c`, `it8951_usb.c/.h`) — Standalone C implementation (no AI)

## Packaging

Uses `pyproject.toml` with optional dependency groups:
- Base: `pillow` (always needed)
- `[ai]`: `google-genai`, `python-dotenv`
- `[gpio]`: `lgpio`
- `[all]`: Everything
- `[dev]`: All + pytest

Entry point: `dreamcam` CLI command or `python -m dreamcam`.

## Hardware Requirements

- Raspberry Pi (Pi 5 uses gpiochip4, older Pi uses gpiochip0)
- IT8951-based e-ink display (1872x1404 resolution) connected via USB
- Pi Camera Module (accessed via `libcamera-still`)
- ImageMagick `convert` command (C version only)

## Remote Access (Raspberry Pi 5)

- SSH alias: `ssh rp5`
- Remote project path: `~/Developer/eink-camera/`
- Remote dreams path: `~/Developer/eink-camera/dreams/`
- Local dreams download: `~/Downloads/dreams/`
- Sync dreams to local: `rsync -avz --ignore-existing rp5:~/Developer/eink-camera/dreams/ ~/Downloads/dreams/`
- Note: The dream camera requires an interactive TTY for keyboard input — cannot be launched headless via tool-based SSH. GPIO button input works regardless.

## Key Conventions

- All display operations require `sudo` (SCSI device access) — except simulator mode
- E-ink device path varies: `/dev/sg0` (Python/SCSI generic) or `/dev/sda` (C version)
- Images are always 8-bit grayscale, 1 byte per pixel
- Python code uses a venv at `./venv/`
- Dream images are saved to `./dreams/` (gitignored)
- `.env` file can hold `GOOGLE_API_KEY` (loaded via python-dotenv)
