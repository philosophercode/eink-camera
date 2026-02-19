"""Web remote control for the dream camera.

Lazy-imports FastAPI so the module is importable even when
uvicorn/fastapi aren't installed.
"""

from __future__ import annotations

import socket
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from dreamcam.app import DreamCamera
    from dreamcam.web.bridge import EventBridge


def get_local_ip() -> str:
    """Get the Pi's local network IP address."""
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
        s.close()
        return ip
    except Exception:
        return "127.0.0.1"


def get_web_url(port: int = 8000) -> str:
    """Get the full URL for the web remote."""
    return f"http://{get_local_ip()}:{port}"


def start_server(camera: DreamCamera, bridge: EventBridge,
                 host: str = "0.0.0.0", port: int = 8000) -> None:
    """Start the web server in a daemon thread."""
    import threading

    from dreamcam.web.server import create_app

    app = create_app(camera, bridge)

    def _run():
        import uvicorn
        uvicorn.run(app, host=host, port=port, log_level="warning")

    thread = threading.Thread(target=_run, daemon=True)
    thread.start()

    url = get_web_url(port)
    print(f"  Web remote: {url}")
