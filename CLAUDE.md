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
pip install -r requirements.txt   # Pillow, google-genai, python-dotenv, lgpio
export GOOGLE_API_KEY="..."       # Required for Gemini AI features
sudo ./dream /dev/sg0             # Launch via wrapper script
sudo python3 dream_camera.py /dev/sg0   # Or run directly
```

## Architecture

Two parallel implementations exist — a C version (simpler, no AI) and a Python version (full-featured):

### IT8951 USB Display Driver
- **C**: `it8951_usb.c` / `it8951_usb.h` — SCSI commands via Linux SG_IO ioctl to IT8951 controller
- **Python**: `eink.py` — `EInkDisplay` class, same protocol using ctypes for SG_IO structs. This is the active driver used by all Python code.

Both drivers communicate with the IT8951 e-ink controller over USB mass storage (SCSI generic interface at `/dev/sg0` or `/dev/sda`). Image data is sent in chunks (max 60800 bytes per transfer) using custom SCSI vendor commands (0xfe prefix). The protocol uses big-endian for coordinates but little-endian for the image buffer address.

### Display Modes
Defined in both drivers: `MODE_INIT` (0, full clear), `MODE_DU` (1, fast 1-bit), `MODE_GC16` (2, 16-level grayscale), `MODE_A2` (4, fast B&W for animation).

### Dream Camera (`dream_camera.py`)
`DreamCamera` class orchestrates: capture via `libcamera-still` -> Gemini API image transformation -> e-ink display. Supports two transform types: **environment styles** (change background, e.g. jungle/space/tokyo) and **art styles** (transform rendering, e.g. clay/pencil/watercolor). Uses `nano-banana-pro-preview` model for image generation. Has a loading spinner animation during AI processing using partial A2 refreshes. Auto-resets display every 10 captures to prevent e-ink freezing.

### GPIO Button Support
Physical button on GPIO17 (configurable) with pull-up resistor. Short press = capture, long hold (1.5s) = enter style cycling mode, double-click or timeout = confirm style.

### Other Files
- `runner.py` — Animated sprite demo (Donkey Kong-style runner with flips) for testing e-ink refresh rates
- `example_simple.py` — Minimal usage examples (test pattern, capture, display image)
- `dream` / `dcam` — Bash launcher scripts that activate the venv

## Hardware Requirements

- Raspberry Pi (Pi 5 uses gpiochip4, older Pi uses gpiochip0)
- IT8951-based e-ink display (1872x1404 resolution) connected via USB
- Pi Camera Module (accessed via `libcamera-still`)
- ImageMagick `convert` command (C version only, for image processing)

## Key Conventions

- All display operations require `sudo` (SCSI device access)
- E-ink device path varies: `/dev/sg0` (Python/SCSI generic) or `/dev/sda` (C version)
- Images are always 8-bit grayscale, 1 byte per pixel
- Python code uses a venv at `./venv/`
- Dream images are saved to `./dreams/` (gitignored)
- `.env` file can hold `GOOGLE_API_KEY` (loaded via python-dotenv)
