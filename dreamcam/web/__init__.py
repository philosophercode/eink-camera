"""Web remote control for the dream camera.

Lazy-imports FastAPI so the module is importable even when
uvicorn/fastapi aren't installed.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from dreamcam.app import DreamCamera
    from dreamcam.web.bridge import EventBridge


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
    print(f"  Web remote: http://{host}:{port}")
