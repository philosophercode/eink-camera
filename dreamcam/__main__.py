"""Entry point for `python -m dreamcam`."""

from __future__ import annotations

import argparse
import os
import sys


def main(argv: list[str] | None = None):
    from dreamcam.display import create_display
    from dreamcam.styles import style_names, DEFAULT_STYLE
    from dreamcam.transform import Transformer
    from dreamcam.app import DreamCamera

    # Load .env if available
    try:
        from dotenv import load_dotenv
        load_dotenv()
    except ImportError:
        pass

    parser = argparse.ArgumentParser(description='AI Dream Camera')
    parser.add_argument('device', nargs='?', default='/dev/sg0',
                        help='E-ink USB device path (default: /dev/sg0)')
    parser.add_argument('--backend', choices=['usb', 'sim'], default='usb',
                        help='Display backend (default: usb)')
    parser.add_argument('--sim-dir', metavar='DIR',
                        help='Simulator output directory (implies --backend sim)')
    parser.add_argument('--once', action='store_true',
                        help='Take one dream photo and exit')
    parser.add_argument('--gpio', type=int, default=17,
                        help='GPIO pin for button (default: 17)')
    parser.add_argument('--no-button', action='store_true',
                        help='Disable physical button')
    parser.add_argument('--style', choices=style_names(), default=DEFAULT_STYLE,
                        help='Dream style')
    parser.add_argument('--save', metavar='DIR', default='./dreams',
                        help='Save images to directory (default: ./dreams)')
    parser.add_argument('--no-save', action='store_true',
                        help='Disable auto-saving images')
    parser.add_argument('--web', action='store_true',
                        help='Enable web remote control')
    parser.add_argument('--web-port', type=int, default=8000,
                        help='Web server port (default: 8000)')
    args = parser.parse_args(argv)

    # Resolve backend
    backend = args.backend
    if args.sim_dir:
        backend = 'sim'

    # Resolve save path
    save_dir = None
    if not args.no_save:
        save_dir = _resolve_save_path(args.save)

    # Create display
    if backend == 'sim':
        display = create_display('sim', output_dir=args.sim_dir)
    else:
        display = create_display('usb', device=args.device)

    # Create transformer
    api_key = os.environ.get('GOOGLE_API_KEY')
    transformer = Transformer(api_key=api_key)

    # Web remote setup (wraps display before passing to DreamCamera)
    bridge = None
    if args.web:
        from dreamcam.web.proxy import DisplayProxy
        from dreamcam.web.bridge import EventBridge
        display = DisplayProxy(display)
        bridge = EventBridge()

    # Create and run camera
    camera = DreamCamera(display=display, transformer=transformer, save_dir=save_dir)

    from dreamcam.styles import get_style
    camera.style = get_style(args.style)

    if args.web:
        from dreamcam.web import start_server, get_web_url
        start_server(camera, bridge, port=args.web_port)
        # Show QR code on e-ink so user can scan to connect
        url = get_web_url(args.web_port)
        camera.screen.show_qr_code(url, duration=0.0)

    if args.once:
        print(f"Style: {camera.style.name}")
        camera.dream_and_display()
        camera.display.close()
    else:
        gpio_pin = None if args.no_button else args.gpio
        try:
            camera.run(gpio_pin=gpio_pin, web_bridge=bridge)
        finally:
            camera.display.close()


def _resolve_save_path(save_path: str) -> str:
    """Resolve save directory, handling sudo and relative paths."""
    if save_path.startswith('~') and os.environ.get('SUDO_USER'):
        import pwd
        real_home = pwd.getpwnam(os.environ['SUDO_USER']).pw_dir
        return save_path.replace('~', real_home, 1)
    elif save_path.startswith('~'):
        return os.path.expanduser(save_path)
    elif not save_path.startswith('/'):
        script_dir = os.path.dirname(os.path.abspath(__file__))
        # Go up one level from dreamcam/ to project root
        project_dir = os.path.dirname(script_dir)
        return os.path.join(project_dir, save_path)
    return save_path


if __name__ == '__main__':
    main()
