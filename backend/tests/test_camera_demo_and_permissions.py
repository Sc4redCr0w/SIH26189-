import time
from pathlib import Path

import cv2
import numpy as np
from fastapi.testclient import TestClient
from sqlalchemy import select

from app.camera_detection import FaceBox
from app.camera_manager import CameraManager
from app.camera_sources import FramePacket
from app.config import get_settings
from app.db import SessionLocal
from app.main import app
from app.models import Camera, CameraObservation, Evidence, Relationship


class DemoSource:
    def __init__(self) -> None:
        self.connected = False
        self.stopped = False
        self.reads = 0

    def connect(self) -> None:
        self.connected = True

    def read_frame(self) -> FramePacket | None:
        if self.stopped or self.reads >= 12:
            return None
        self.reads += 1
        return FramePacket(frame=np.zeros((120, 160, 3), dtype=np.uint8), frame_number=self.reads, timestamp_seconds=self.reads * 0.2)

    def is_alive(self) -> bool:
        return self.connected and not self.stopped

    def stop(self) -> None:
        self.stopped = True

    def reconnect(self) -> None:
        self.connected = True


class NoDetectionDetector:
    name = "no-detection"
    confidence_method = "TEST_DOUBLE"
    available = True

    def detect(self, frame):  # noqa: ANN001, ANN201
        return []


def auth(client: TestClient, username: str, password: str) -> dict[str, str]:
    response = client.post("/api/v1/auth/login", json={"username": username, "password": password})
    assert response.status_code == 200, response.text
    return {"Authorization": f"Bearer {response.json()['access_token']}"}


def test_role_permissions_are_enforced_server_side() -> None:
    with TestClient(app) as client:
        admin = auth(client, "admin", "ChangeMe-Admin-2026!")
        analyst = auth(client, "analyst", "ChangeMe-Analyst-2026!")
        auditor = auth(client, "auditor", "ChangeMe-Auditor-2026!")

        created = client.post(
            "/api/v1/cameras",
            headers=admin,
            json={"camera_name": "Permission Camera", "source_type": "WEBCAM", "source_uri": "0", "location_name": "Permission Gate"},
        )
        assert created.status_code == 201
        camera_id = created.json()["id"]

        assert client.get("/api/v1/cameras", headers=auditor).status_code == 200
        assert client.get("/api/v1/cameras/observations/all", headers=auditor).status_code == 200

        # Analyst and Auditor cannot change camera configuration or stream state.
        assert client.patch(f"/api/v1/cameras/{camera_id}", headers=analyst, json={"camera_name": "Renamed"}).status_code == 403
        assert client.patch(f"/api/v1/cameras/{camera_id}", headers=auditor, json={"camera_name": "Renamed"}).status_code == 403
        assert client.post(f"/api/v1/cameras/{camera_id}/start", headers=analyst).status_code == 403
        assert client.post(f"/api/v1/cameras/{camera_id}/stop", headers=auditor).status_code == 403
        assert client.delete(f"/api/v1/cameras/{camera_id}", headers=analyst).status_code == 403
        assert client.get(f"/api/v1/cameras/{camera_id}", headers=analyst).json()["camera_name"] == "Permission Camera"

        # Auditor is read-only on reviews.
        assert client.post("/api/v1/cameras/observations/OBS-X/review", headers=auditor, json={"decision": "VERIFY"}).status_code == 403


def test_demo_simulation_creates_labeled_observation_without_identity_link(monkeypatch) -> None:
    settings = get_settings()
    monkeypatch.setattr(settings, "camera_demo_mode", True, raising=False)
    monkeypatch.setattr(settings, "camera_frame_interval_seconds", 0.01, raising=False)
    monkeypatch.setattr(settings, "camera_detection_cooldown_seconds", 30.0, raising=False)

    with TestClient(app) as client:
        admin = auth(client, "admin", "ChangeMe-Admin-2026!")
        created = client.post(
            "/api/v1/cameras",
            headers=admin,
            json={
                "camera_name": "Demo Simulation Camera",
                "source_type": "VIDEO_FILE",
                "source_uri": str(__file__),
                "location_name": "Demo Location",
                "metadata": {
                    "demo_events": [
                        {
                            "timestamp_seconds": 0.5,
                            "bbox": {"x": 30, "y": 20, "width": 60, "height": 70},
                            "confidence": 0.97,
                            "label": "Potential match event — SIMULATED",
                            "suggested_person_id": "ENT-DEMO-P1001",
                        }
                    ]
                },
            },
        )
        # A non-video file must be rejected by source validation.
        assert created.status_code == 422
        created = client.post(
            "/api/v1/cameras",
            headers=admin,
            json={
                "camera_name": "Demo Simulation Camera",
                "source_type": "WEBCAM",
                "source_uri": "0",
                "location_name": "Demo Location",
                "metadata": {
                    "demo_events": [
                        {
                            "timestamp_seconds": 0.5,
                            "bbox": {"x": 30, "y": 20, "width": 60, "height": 70},
                            "confidence": 0.97,
                            "label": "Potential match event — SIMULATED",
                            "suggested_person_id": "ENT-DEMO-P1001",
                        }
                    ]
                },
            },
        )
        assert created.status_code == 201, created.text
        camera_id = created.json()["id"]

    manager = CameraManager(source_factory=lambda camera: DemoSource(), detector_factory=NoDetectionDetector)
    try:
        runtime = manager.start_camera(camera_id)
        deadline = time.time() + 8
        while time.time() < deadline and runtime.detection_count < 1:
            time.sleep(0.1)
        assert runtime.detection_count >= 1
    finally:
        manager.stop_all()

    with SessionLocal() as db:
        observation = db.scalar(select(CameraObservation).where(CameraObservation.camera_id == camera_id).order_by(CameraObservation.created_at.desc()))
        assert observation is not None
        assert observation.is_simulated is True
        assert "SIMULATED" in observation.simulation_label.upper()
        assert observation.suggested_person_id == "ENT-DEMO-P1001"
        assert observation.review_status == "PENDING_REVIEW"
        assert observation.detection_confidence == 0.97
        assert observation.metadata_json["demo_simulation_not_biometric_identification"] is True
        # The saved annotated frame must actually contain the drawn box.
        raw_bytes = Path(db.get(Evidence, observation.evidence_id).storage_path).read_bytes()
        annotated_bytes = Path(db.get(Evidence, observation.annotated_evidence_id).storage_path).read_bytes()
        assert raw_bytes and annotated_bytes and raw_bytes != annotated_bytes
        decoded = cv2.imdecode(np.frombuffer(annotated_bytes, np.uint8), cv2.IMREAD_COLOR)
        box_region = decoded[observation.bbox_y : observation.bbox_y + observation.bbox_height, observation.bbox_x : observation.bbox_x + observation.bbox_width]
        assert box_region.size and int(box_region.max()) > 0
        # A simulated hint must not create a person relationship on its own.
        person_link = db.scalar(
            select(Relationship).where(
                Relationship.relationship_type == "HUMAN_VERIFIED_OBSERVATION",
                Relationship.target_id == observation.id,
            )
        )
        assert person_link is None
        observation_id = observation.id

    # A human review is still required before the graph receives an association.
    with TestClient(app) as client:
        analyst = auth(client, "analyst", "ChangeMe-Analyst-2026!")
        review = client.post(
            f"/api/v1/cameras/observations/{observation_id}/review",
            headers=analyst,
            json={"decision": "ASSOCIATE", "associated_person_id": "ENT-DEMO-P1001", "notes": "Human reviewer confirmed the simulated event."},
        )
        assert review.status_code == 200, review.text
        assert review.json()["review_status"] == "ASSOCIATED_WITH_ENTITY"
    with SessionLocal() as db:
        person_link = db.scalar(
            select(Relationship).where(
                Relationship.relationship_type == "HUMAN_VERIFIED_OBSERVATION",
                Relationship.target_id == observation_id,
                Relationship.source_id == "ENT-DEMO-P1001",
            )
        )
        assert person_link is not None
        assert person_link.evidence_id is not None
        assert "not biometric identification" in person_link.notes.lower()


def test_person_reference_photo_is_stored_for_human_review_only() -> None:
    png_bytes = (
        b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01\x08\x06\x00\x00\x00\x1f\x15\xc4\x89"
        b"\x00\x00\x00\nIDATx\x9cc\x00\x01\x00\x00\x05\x00\x01\r\n-\xb4\x00\x00\x00\x00IEND\xaeB`\x82"
    )
    with TestClient(app) as client:
        admin = auth(client, "admin", "ChangeMe-Admin-2026!")
        analyst = auth(client, "analyst", "ChangeMe-Analyst-2026!")
        upload = client.post(
            "/api/v1/cameras/entities/ENT-DEMO-P1001/reference-photo",
            headers=admin,
            files={"file": ("photo.png", png_bytes, "image/png")},
            data={"label": "Reference photo 01", "notes": "Record photo"},
        )
        assert upload.status_code == 201, upload.text
        photo = upload.json()
        assert photo["entity_id"] == "ENT-DEMO-P1001"
        assert client.get(f"/api/v1/cameras/entities/ENT-DEMO-P1001/reference-photos", headers=analyst).status_code == 200
        blocked = client.post(
            "/api/v1/cameras/entities/ENT-DEMO-P1001/reference-photo",
            headers=analyst,
            files={"file": ("photo.png", png_bytes, "image/png")},
        )
        assert blocked.status_code == 403
        bad_target = client.post(
            "/api/v1/cameras/entities/ENT-NOT-A-PERSON/reference-photo",
            headers=admin,
            files={"file": ("photo.png", png_bytes, "image/png")},
        )
        assert bad_target.status_code == 404
        audit = client.get("/api/v1/audit?action=PERSON_REFERENCE_PHOTO_ADDED", headers=admin)
        assert audit.status_code == 200 and audit.json()


def test_malformed_demo_event_metadata_is_rejected_at_configuration_time() -> None:
    with TestClient(app) as client:
        admin = auth(client, "admin", "ChangeMe-Admin-2026!")
        base = {"camera_name": "Metadata Validation Camera", "source_type": "WEBCAM", "source_uri": "0", "location_name": "Validation Gate"}
        cases = [
            {"demo_events": "4.0"},
            {"demo_events": ["not-an-object"]},
            {"demo_events": [{"timestamp_seconds": "soon", "bbox": {"x": 1, "y": 1, "width": 10, "height": 10}}]},
            {"demo_events": [{"timestamp_seconds": 1.0, "bbox": "not-an-object"}]},
            {"demo_events": [{"timestamp_seconds": 1.0, "suggested_person_id": 7}]},
        ]
        for metadata in cases:
            response = client.post("/api/v1/cameras", headers=admin, json={**base, "metadata": metadata})
            assert response.status_code == 422, f"{metadata} -> {response.status_code} {response.text}"
        valid = client.post(
            "/api/v1/cameras",
            headers=admin,
            json={**base, "camera_name": "Metadata Validation Camera OK", "metadata": {"demo_events": [{"timestamp_seconds": 2.5, "bbox": {"x": 10, "y": 10, "width": 40, "height": 50}, "label": "Potential match event - SIMULATED", "suggested_person_id": "ENT-DEMO-P1001"}]}},
        )
        assert valid.status_code == 201, valid.text
        assert isinstance(valid.json()["metadata"]["demo_events"], list)
