from __future__ import annotations

import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Protocol
from urllib.parse import unquote, urlparse

from .config import get_settings


@dataclass
class FramePacket:
    frame: Any
    frame_number: int
    timestamp_seconds: float


class CameraSource(Protocol):
    def connect(self) -> None: ...
    def read_frame(self) -> FramePacket | None: ...
    def is_alive(self) -> bool: ...
    def stop(self) -> None: ...
    def reconnect(self) -> None: ...


class OpenCVSource:
    def __init__(self, source: Any, *, loop: bool = False) -> None:
        self.source = source
        self.loop = loop
        self.capture: Any | None = None
        self.frame_number = 0
        self.started_at = time.monotonic()

    def connect(self) -> None:
        try:
            import cv2  # type: ignore[import-not-found]
        except ImportError as exc:  # pragma: no cover - dependency is optional for API-only use
            raise RuntimeError("OpenCV is required for camera streaming") from exc
        self.capture = cv2.VideoCapture(self.source)
        if not self.capture or not self.capture.isOpened():
            self.capture.release() if self.capture else None
            self.capture = None
            raise RuntimeError(f"Unable to open camera source: {self.source}")
        self.frame_number = 0
        self.started_at = time.monotonic()

    def read_frame(self) -> FramePacket | None:
        if self.capture is None:
            return None
        ok, frame = self.capture.read()
        if not ok or frame is None:
            if not self.loop:
                return None
            self.capture.set(1, 0)
            ok, frame = self.capture.read()
            if not ok or frame is None:
                return None
        self.frame_number += 1
        return FramePacket(frame=frame, frame_number=self.frame_number, timestamp_seconds=time.monotonic() - self.started_at)

    def is_alive(self) -> bool:
        return bool(self.capture is not None and self.capture.isOpened())

    def stop(self) -> None:
        if self.capture is not None:
            self.capture.release()
            self.capture = None

    def reconnect(self) -> None:
        self.stop()
        time.sleep(0.25)
        self.connect()


class WebcamSource(OpenCVSource):
    def __init__(self, source_uri: str) -> None:
        try:
            index = int(source_uri.strip())
        except ValueError as exc:
            raise ValueError("WEBCAM source_uri must be a camera index such as 0") from exc
        super().__init__(index, loop=False)


class VideoFileSource(OpenCVSource):
    def __init__(self, source_uri: str, *, loop: bool = True) -> None:
        settings = get_settings()
        raw = source_uri.strip()
        if raw.startswith("file://"):
            raw = unquote(urlparse(raw).path)
        path = Path(raw)
        if not path.is_absolute():
            path = settings.project_root / path
        path = path.resolve()
        if not path.is_file():
            raise ValueError(f"VIDEO_FILE does not exist: {path}")
        if path.suffix.lower() not in {".mp4", ".avi", ".mov", ".mkv", ".webm"}:
            raise ValueError("VIDEO_FILE must be a local video file")
        super().__init__(str(path), loop=loop)


class HttpStreamSource(OpenCVSource):
    def __init__(self, source_uri: str) -> None:
        parsed = urlparse(source_uri.strip())
        if parsed.scheme not in {"http", "https"}:
            raise ValueError("HTTP_STREAM source_uri must use http:// or https://")
        super().__init__(source_uri.strip(), loop=False)


class RTSPSource(OpenCVSource):
    def __init__(self, source_uri: str) -> None:
        parsed = urlparse(source_uri.strip())
        if parsed.scheme not in {"rtsp", "rtsps"}:
            raise ValueError("RTSP source_uri must use rtsp:// or rtsps://")
        super().__init__(source_uri.strip(), loop=False)


def create_camera_source(camera: Any, *, loop_video: bool = True) -> CameraSource:
    source_type = camera.source_type.upper()
    if source_type == "WEBCAM":
        return WebcamSource(camera.source_uri)
    if source_type == "VIDEO_FILE":
        return VideoFileSource(camera.source_uri, loop=loop_video)
    if source_type == "HTTP_STREAM":
        return HttpStreamSource(camera.source_uri)
    if source_type == "RTSP":
        return RTSPSource(camera.source_uri)
    raise ValueError(f"Unsupported camera source type: {source_type}")
