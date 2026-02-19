"""FastAPI web server for smartphone remote control."""

from __future__ import annotations

import asyncio
import io
import os
from typing import TYPE_CHECKING

from fastapi import FastAPI, File, HTTPException, UploadFile
from fastapi.responses import JSONResponse, Response, StreamingResponse
from fastapi.staticfiles import StaticFiles

if TYPE_CHECKING:
    from dreamcam.app import DreamCamera
    from dreamcam.web.bridge import EventBridge


def create_app(camera: DreamCamera, bridge: EventBridge) -> FastAPI:
    app = FastAPI(title="DreamCam Remote")

    @app.get("/api/status")
    def get_status():
        return {
            "status": bridge.status.value,
            "style": camera.style.name,
            "capture_count": camera.capture_count,
            "error": bridge.last_error,
        }

    @app.get("/api/styles")
    def get_styles():
        from dreamcam.styles import STYLES
        return [
            {"name": s.name, "category": s.category, "prompt": s.prompt}
            for s in STYLES
        ]

    @app.post("/api/capture")
    def trigger_capture():
        if bridge.status.value not in ("idle", "done"):
            raise HTTPException(409, "Camera is busy")
        bridge.send_command("capture")
        return {"ok": True}

    @app.post("/api/style/{style_name}")
    def set_style(style_name: str):
        from dreamcam.styles import get_style
        try:
            get_style(style_name)
        except KeyError:
            raise HTTPException(404, f"Unknown style: {style_name}")
        bridge.send_command("set_style", style_name)
        return {"ok": True, "style": style_name}

    @app.post("/api/upload")
    async def upload_photo(file: UploadFile = File(...)):
        if bridge.status.value not in ("idle", "done"):
            raise HTTPException(409, "Camera is busy")
        from PIL import Image
        contents = await file.read()
        try:
            image = Image.open(io.BytesIO(contents))
            image.load()  # force decode to catch corrupt files
        except Exception:
            raise HTTPException(400, "Invalid image")
        bridge.send_command("upload_dream", image)
        return {"ok": True}

    @app.get("/api/preview")
    def get_preview():
        from dreamcam.web.proxy import DisplayProxy
        if not isinstance(camera.display, DisplayProxy):
            raise HTTPException(501, "Preview not available (no DisplayProxy)")
        jpeg_bytes, version = camera.display.snapshot
        if not jpeg_bytes:
            raise HTTPException(204, "No content yet")
        return Response(
            content=jpeg_bytes,
            media_type="image/jpeg",
            headers={
                "X-Preview-Version": str(version),
                "Cache-Control": "no-cache",
            },
        )

    @app.get("/api/preview/version")
    def get_preview_version():
        from dreamcam.web.proxy import DisplayProxy
        if isinstance(camera.display, DisplayProxy):
            _, version = camera.display.snapshot
            return {"version": version}
        return {"version": -1}

    @app.get("/api/gallery")
    def list_gallery():
        from dreamcam.gallery import Gallery
        gallery = Gallery(camera.save_dir)
        images = gallery.load()
        return [
            {"filename": os.path.basename(p)}
            for p in images
        ]

    @app.get("/api/gallery/{filename}")
    def get_gallery_image(filename: str):
        if not camera.save_dir:
            raise HTTPException(404, "No save directory")
        if "/" in filename or "\\" in filename or ".." in filename:
            raise HTTPException(400, "Invalid filename")
        path = os.path.join(camera.save_dir, filename)
        if not os.path.isfile(path):
            raise HTTPException(404, "Image not found")
        with open(path, "rb") as f:
            data = f.read()
        return Response(content=data, media_type="image/jpeg")

    @app.get("/api/events")
    async def event_stream():
        async def generate():
            last_status = None
            last_version = -1
            while True:
                current_status = bridge.status.value
                if current_status != last_status:
                    last_status = current_status
                    error = bridge.last_error or ""
                    yield f"event: status\ndata: {current_status}\n\n"
                    if current_status == "error" and error:
                        yield f"event: error\ndata: {error}\n\n"

                from dreamcam.web.proxy import DisplayProxy
                if isinstance(camera.display, DisplayProxy):
                    _, version = camera.display.snapshot
                    if version != last_version:
                        last_version = version
                        yield f"event: preview\ndata: {version}\n\n"

                await asyncio.sleep(0.5)

        return StreamingResponse(
            generate(),
            media_type="text/event-stream",
            headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
        )

    # Static files (catch-all, must be last)
    static_dir = os.path.join(os.path.dirname(__file__), "static")
    app.mount("/", StaticFiles(directory=static_dir, html=True), name="static")

    return app
