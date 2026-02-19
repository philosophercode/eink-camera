"""EventBridge -- thread-safe communication between web server and camera loop."""

from __future__ import annotations

import queue
import threading
from dataclasses import dataclass
from enum import Enum
from typing import Any


class CameraStatus(str, Enum):
    IDLE = "idle"
    CAPTURING = "capturing"
    DREAMING = "dreaming"
    DONE = "done"
    ERROR = "error"


@dataclass
class WebCommand:
    """A command from the web UI to the camera."""
    action: str       # "capture", "set_style", "upload_dream"
    payload: Any = None


class EventBridge:
    """Shared state and command queue between web server and camera main loop."""

    def __init__(self):
        self._commands: queue.Queue[WebCommand] = queue.Queue()
        self._status = CameraStatus.IDLE
        self._status_lock = threading.Lock()
        self._status_event = threading.Event()
        self._last_error: str | None = None

    # -- Called from web server thread --

    def send_command(self, action: str, payload: Any = None):
        """Queue a command for the camera main loop."""
        self._commands.put(WebCommand(action=action, payload=payload))

    @property
    def status(self) -> CameraStatus:
        with self._status_lock:
            return self._status

    @property
    def last_error(self) -> str | None:
        with self._status_lock:
            return self._last_error

    def wait_for_status_change(self, timeout: float = 30.0) -> bool:
        """Block until status changes. Returns True if changed, False on timeout."""
        self._status_event.clear()
        return self._status_event.wait(timeout)

    # -- Called from camera main loop thread --

    def poll_command(self) -> WebCommand | None:
        """Non-blocking: return next command or None."""
        try:
            return self._commands.get_nowait()
        except queue.Empty:
            return None

    def set_status(self, status: CameraStatus, error: str | None = None):
        """Update the camera status (from main loop)."""
        with self._status_lock:
            self._status = status
            self._last_error = error
        self._status_event.set()
