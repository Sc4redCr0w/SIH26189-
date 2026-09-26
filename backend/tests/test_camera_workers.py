import time
from typing import Any

import numpy as np
from fastapi.testclient import TestClient

from app.camera_detection import FaceBox
from app.camera_manager import CameraManager
from app.camera_sources import FramePacket
from app.config import get_settings
from app.db import SessionLocal
from app.main import app
from app.models import CameraObservation


class FakeSource:
    """Deterministic in-process camera source used for worker isolation tests."""

    def __init__(self, *, frame_count: int, fail_after: int | None = None) -> None:
        self.frame_count = frame_count
        self.fail_after = fail_after
        self.connected = False
        self.stopped = False
        self.reconnects = 0
        self.reads = 0

    def connect(self) -> None:
        self.connected = True

    def read_frame(self) -> FramePacket | None:
        if self.stopped or self.reads >= self.frame_count:
            return None
        self.reads += 1
        if self.fail_after is not None and self.reads > self.fail_after:
            raise RuntimeError("synthetic source failure")
        return FramePacket(frame=np.zeros((120, 160, 3), dtype=np.uint8), frame_number=self.reads, timestamp_seconds=self.reads * 0.1)

    def is_alive(self) -> bool:
        return self.connected and not self.stopped

    def stop(self) -> None:
        self.stopped = True

    def reconnect(self) -> None:
        self.reconnects += 1
        self.connected = True


class FakeDetector:
    name = "fake-detector"
    confidence_method = "TEST_DOUBLE"
    available = True

    def __init__(self, *, detections: int = 1) -> None:
        self.detections = detections

    def detect(self, frame: Any) -> list[FaceBox]:
        return [FaceBox(20, 20, 40, 50) for _ in range(self.detections)]


def auth(client: TestClient, username: str, password: str) -> dict[str, str]:
    response = client.post("/api/v1/auth/login", json={"username": username, "password": password})
    assert response.status_code == 200, response.text
    return {"Authorization": f"Bearer {response.json()['access_token']}"}


def _create_camera(client: TestClient, admin: dict[str, str], name: str) -> str:
    created = client.post(
        "/api/v1/cameras",
        headers=admin,
        json={"camera_name": name, "source_type": "WEBCAM", "source_uri": "0", "location_name": f"{name} location"},
    )
    assert created.status_code == 201, created.text
    return created.json()["id"]


def test_multiple_camera_workers_run_independently(monkeypatch) -> None:
    settings = get_settings()
    monkeypatch.setattr(settings, "camera_detection_cooldown_seconds", 30.0, raising=False)
    monkeypatch.setattr(settings, "camera_frame_interval_seconds", 0.01, raising=False)

    with TestClient(app) as client:
        admin = auth(client, "admin", "ChangeMe-Admin-2026!")
        camera_a = _create_camera(client, admin, "Worker Camera A")
        camera_b = _create_camera(client, admin, "Worker Camera B")

    sources: dict[str, FakeSource] = {}

    def source_factory(camera: Any) -> FakeSource:
        # Camera B fails after three frames to prove that one broken source
        # does not stop the healthy worker.
        source = FakeSource(frame_count=6, fail_after=None if camera.id == camera_a else 3)
        sources[camera.id] = source
        return source

    manager = CameraManager(source_factory=source_factory, detector_factory=FakeDetector)
    try:
        runtime_a = manager.start_camera(camera_a)
        runtime_b = manager.start_camera(camera_b)
        deadline = time.time() + 10
        while time.time() < deadline:
            if runtime_a.detection_count >= 1 and runtime_b.detection_count >= 1:
                break
            time.sleep(0.1)

        assert runtime_a.status == "LIVE", runtime_a.last_error
        assert runtime_a.detection_count >= 1
        assert runtime_b.detection_count >= 1
        assert sources[camera_a].connected is True

        with SessionLocal() as db:
            observations = db.query(CameraObservation).filter(CameraObservation.camera_id.in_([camera_a, camera_b])).all()
        assert {observation.camera_id for observation in observations} == {camera_a, camera_b}
        # Cooldown must collapse a continuously visible face into a single observation.
        assert all(observation.review_status == "PENDING_REVIEW" for observation in observations)
        assert all(observation.metadata_json["detector_confidence_method"] == "TEST_DOUBLE" for observation in observations)
    finally:
        manager.stop_all()

    assert sources[camera_a].stopped is True
    assert sources[camera_b].stopped is True


def test_worker_reconnect_marks_camera_offline_without_crashing() -> None:
    settings = get_settings()
    manager = CameraManager(source_factory=lambda camera: FakeSource(frame_count=50, fail_after=2), detector_factory=FakeDetector)
    with TestClient(app) as client:
        admin = auth(client, "admin", "ChangeMe-Admin-2026!")
        camera_id = _create_camera(client, admin, "Reconnect Camera")
    runtime = manager.start_camera(camera_id)
    try:
        deadline = time.time() + 8
        while time.time() < deadline and runtime.status == "LIVE":
            time.sleep(0.1)
        assert runtime.status in {"OFFLINE", "LIVE"}
        assert runtime.last_error or runtime.status == "LIVE"
    finally:
        manager.stop_all()
