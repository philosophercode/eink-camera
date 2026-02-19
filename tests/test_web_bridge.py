"""Tests for EventBridge."""

import threading
import time

from dreamcam.web.bridge import CameraStatus, EventBridge, WebCommand


class TestEventBridge:

    def test_send_and_poll_command(self):
        bridge = EventBridge()
        bridge.send_command("capture")
        cmd = bridge.poll_command()
        assert cmd is not None
        assert cmd.action == "capture"
        assert cmd.payload is None

    def test_send_command_with_payload(self):
        bridge = EventBridge()
        bridge.send_command("set_style", "watercolor")
        cmd = bridge.poll_command()
        assert cmd.action == "set_style"
        assert cmd.payload == "watercolor"

    def test_poll_returns_none_when_empty(self):
        bridge = EventBridge()
        assert bridge.poll_command() is None

    def test_commands_are_fifo(self):
        bridge = EventBridge()
        bridge.send_command("capture")
        bridge.send_command("set_style", "clay")
        bridge.send_command("capture")

        assert bridge.poll_command().action == "capture"
        assert bridge.poll_command().action == "set_style"
        assert bridge.poll_command().action == "capture"
        assert bridge.poll_command() is None

    def test_initial_status_is_idle(self):
        bridge = EventBridge()
        assert bridge.status == CameraStatus.IDLE

    def test_set_and_get_status(self):
        bridge = EventBridge()
        bridge.set_status(CameraStatus.DREAMING)
        assert bridge.status == CameraStatus.DREAMING

    def test_set_status_with_error(self):
        bridge = EventBridge()
        bridge.set_status(CameraStatus.ERROR, "something broke")
        assert bridge.status == CameraStatus.ERROR
        assert bridge.last_error == "something broke"

    def test_wait_for_status_change(self):
        bridge = EventBridge()
        result = [None]

        def updater():
            time.sleep(0.1)
            bridge.set_status(CameraStatus.CAPTURING)

        t = threading.Thread(target=updater)
        t.start()
        changed = bridge.wait_for_status_change(timeout=2.0)
        t.join()
        assert changed is True
        assert bridge.status == CameraStatus.CAPTURING

    def test_wait_for_status_change_timeout(self):
        bridge = EventBridge()
        changed = bridge.wait_for_status_change(timeout=0.1)
        assert changed is False
