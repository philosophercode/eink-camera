"""Tests for the FastAPI web server."""

from __future__ import annotations

import io
import os
from unittest.mock import MagicMock

import pytest
from PIL import Image

from dreamcam.display.sim import SimDisplay
from dreamcam.styles import DEFAULT_STYLE, get_style
from dreamcam.web.bridge import CameraStatus, EventBridge
from dreamcam.web.proxy import DisplayProxy
from dreamcam.web.server import create_app


@pytest.fixture
def camera_and_bridge(tmp_path):
    """Create a minimal DreamCamera with DisplayProxy and EventBridge."""
    sim = SimDisplay(width=200, height=150)
    proxy = DisplayProxy(sim)
    bridge = EventBridge()

    # Build a mock camera that has the attributes the server reads
    camera = MagicMock()
    camera.display = proxy
    camera.style = get_style(DEFAULT_STYLE)
    camera.capture_count = 0
    camera.save_dir = str(tmp_path / "dreams")
    os.makedirs(camera.save_dir, exist_ok=True)

    return camera, bridge


@pytest.fixture
def client(camera_and_bridge):
    from fastapi.testclient import TestClient
    camera, bridge = camera_and_bridge
    app = create_app(camera, bridge)
    return TestClient(app), camera, bridge


class TestStatusRoute:

    def test_get_status(self, client):
        tc, camera, bridge = client
        res = tc.get("/api/status")
        assert res.status_code == 200
        data = res.json()
        assert data["status"] == "idle"
        assert data["style"] == DEFAULT_STYLE
        assert data["capture_count"] == 0

    def test_status_reflects_bridge(self, client):
        tc, camera, bridge = client
        bridge.set_status(CameraStatus.DREAMING)
        res = tc.get("/api/status")
        assert res.json()["status"] == "dreaming"


class TestStyleRoutes:

    def test_get_styles(self, client):
        tc, _, _ = client
        res = tc.get("/api/styles")
        assert res.status_code == 200
        styles = res.json()
        assert len(styles) > 10
        assert all("name" in s and "category" in s for s in styles)

    def test_set_valid_style(self, client):
        tc, _, bridge = client
        res = tc.post("/api/style/watercolor")
        assert res.status_code == 200
        assert res.json()["style"] == "watercolor"
        cmd = bridge.poll_command()
        assert cmd.action == "set_style"
        assert cmd.payload == "watercolor"

    def test_set_invalid_style(self, client):
        tc, _, _ = client
        res = tc.post("/api/style/nonexistent")
        assert res.status_code == 404


class TestCaptureRoute:

    def test_trigger_capture(self, client):
        tc, _, bridge = client
        res = tc.post("/api/capture")
        assert res.status_code == 200
        cmd = bridge.poll_command()
        assert cmd.action == "capture"

    def test_capture_when_busy(self, client):
        tc, _, bridge = client
        bridge.set_status(CameraStatus.DREAMING)
        res = tc.post("/api/capture")
        assert res.status_code == 409


class TestUploadRoute:

    def test_upload_valid_image(self, client):
        tc, _, bridge = client
        img = Image.new('RGB', (100, 100), 'red')
        buf = io.BytesIO()
        img.save(buf, format='JPEG')
        buf.seek(0)
        res = tc.post("/api/upload", files={"file": ("photo.jpg", buf, "image/jpeg")})
        assert res.status_code == 200
        cmd = bridge.poll_command()
        assert cmd.action == "upload_dream"
        assert isinstance(cmd.payload, Image.Image)

    def test_upload_invalid_data(self, client):
        tc, _, _ = client
        res = tc.post("/api/upload",
                       files={"file": ("bad.txt", b"not an image", "text/plain")})
        assert res.status_code == 400

    def test_upload_when_busy(self, client):
        tc, _, bridge = client
        bridge.set_status(CameraStatus.CAPTURING)
        img = Image.new('RGB', (100, 100), 'red')
        buf = io.BytesIO()
        img.save(buf, format='JPEG')
        buf.seek(0)
        res = tc.post("/api/upload", files={"file": ("photo.jpg", buf, "image/jpeg")})
        assert res.status_code == 409


class TestPreviewRoutes:

    def test_get_preview(self, client):
        tc, camera, _ = client
        # Show an image so there's a snapshot
        camera.display.show_image(Image.new('L', (200, 150), 128))
        res = tc.get("/api/preview")
        assert res.status_code == 200
        assert res.headers["content-type"] == "image/jpeg"
        assert "X-Preview-Version" in res.headers

    def test_get_preview_version(self, client):
        tc, _, _ = client
        res = tc.get("/api/preview/version")
        assert res.status_code == 200
        assert "version" in res.json()


class TestGalleryRoutes:

    def test_list_empty_gallery(self, client):
        tc, _, _ = client
        res = tc.get("/api/gallery")
        assert res.status_code == 200
        assert res.json() == []

    def test_list_gallery_with_images(self, client):
        tc, camera, _ = client
        # Create some fake dream images
        Image.new('RGB', (100, 100)).save(
            os.path.join(camera.save_dir, "2025-01-01_12-00-00_clay.jpg"))
        Image.new('RGB', (100, 100)).save(
            os.path.join(camera.save_dir, "2025-01-01_12-00-00_original.jpg"))
        res = tc.get("/api/gallery")
        images = res.json()
        # Should exclude _original
        assert len(images) == 1
        assert images[0]["filename"] == "2025-01-01_12-00-00_clay.jpg"

    def test_get_gallery_image(self, client):
        tc, camera, _ = client
        path = os.path.join(camera.save_dir, "test_dream.jpg")
        Image.new('RGB', (100, 100), 'blue').save(path)
        res = tc.get("/api/gallery/test_dream.jpg")
        assert res.status_code == 200
        assert res.headers["content-type"] == "image/jpeg"

    def test_get_gallery_image_not_found(self, client):
        tc, _, _ = client
        res = tc.get("/api/gallery/nonexistent.jpg")
        assert res.status_code == 404

    def test_path_traversal_rejected(self, client):
        tc, _, _ = client
        # URL-encoded path traversal attempt
        res = tc.get("/api/gallery/..%2Fetc%2Fpasswd")
        assert res.status_code in (400, 404)
        # Direct dotdot in filename
        res = tc.get("/api/gallery/..secret.jpg")
        assert res.status_code == 400
