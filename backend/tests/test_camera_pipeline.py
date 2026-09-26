from datetime import UTC, datetime
from pathlib import Path
from uuid import uuid4

import cv2
import numpy as np
from fastapi.testclient import TestClient

from app.camera_detection import FaceBox, FaceDetector, annotate_frame, box_label, is_simulated
from app.camera_manager import DetectionCooldown
from app.camera_service import create_camera_observation
from app.camera_sources import VideoFileSource
from app.db import SessionLocal
from app.main import app
from app.models import Camera, Evidence


def auth(client: TestClient, username: str, password: str) -> dict[str, str]:
    response = client.post("/api/v1/auth/login", json={"username": username, "password": password})
    assert response.status_code == 200, response.text
    return {"Authorization": f"Bearer {response.json()['access_token']}"}


def test_face_detector_and_bounding_box_overlay_are_detection_only() -> None:
    class FakeCascade:
        def detectMultiScale(self, *_args, **_kwargs):
            return [(40, 30, 80, 95)]

    frame = np.zeros((240, 320, 3), dtype=np.uint8)
    detector = FaceDetector(cascade=FakeCascade())
    detections = detector.detect(frame)
    assert len(detections) == 1
    assert detections[0].as_dict()["label"] == "Face detected"
    assert detections[0].confidence is None
    annotated = annotate_frame(frame, detections)
    assert annotated.shape == frame.shape
    assert int(annotated.sum()) > 0


def test_overlay_labels_distinguish_real_detections_from_simulations() -> None:
    real = FaceBox(10, 10, 40, 40)
    scored = FaceBox(10, 10, 40, 40, confidence=0.94)
    simulated = FaceBox(10, 10, 40, 40, confidence=0.97, label="Potential match event — SIMULATED")
    assert is_simulated(real) is False
    assert is_simulated(simulated) is True
    # A real detection is never relabeled as a simulation, even in demo mode.
    assert box_label(real) == "Face detected"
    assert box_label(scored) == "Face detected 94%"
    assert box_label(simulated) == "DEMO SIMULATION - NOT BIOMETRIC IDENTIFICATION"
    frame = np.zeros((240, 320, 3), dtype=np.uint8)
    real_placed = FaceBox(20, 20, 40, 40)
    simulated_placed = FaceBox(120, 120, 40, 40, confidence=0.97, label="Potential match event — SIMULATED")
    annotated = annotate_frame(frame, [real_placed, simulated_placed], demo_mode=True)
    # Both boxes are drawn, each in its own colour: teal for a real detection,
    # warning red for a simulated event.
    real_border = annotated[20, 20]
    simulated_border = annotated[120, 120]
    assert int(real_border[1]) > 200 and int(simulated_border[2]) > 200
    assert int(simulated_border[1]) < 120


def test_detection_cooldown_throttles_continuous_detections() -> None:
    cooldown = DetectionCooldown(10)
    assert cooldown.should_emit(100.0) is True
    assert cooldown.should_emit(105.0) is False
    assert cooldown.should_emit(110.0) is True


def test_video_file_source_reads_local_video() -> None:
    suffix = uuid4().hex[:8]
    path = Path(__file__).resolve().parents[2] / "backend" / "data" / f"camera-test-{suffix}.mp4"
    path.parent.mkdir(parents=True, exist_ok=True)
    writer = cv2.VideoWriter(str(path), cv2.VideoWriter_fourcc(*"mp4v"), 5.0, (160, 120))
    for _ in range(3):
        writer.write(np.zeros((120, 160, 3), dtype=np.uint8))
    writer.release()
    try:
        source = VideoFileSource(str(path), loop=True)
        source.connect()
        packet = source.read_frame()
        assert packet is not None
        assert packet.frame.shape == (120, 160, 3)
        assert packet.frame_number == 1
        source.stop()
    finally:
        path.unlink(missing_ok=True)


def test_observation_evidence_review_and_human_association() -> None:
    with TestClient(app) as client:
        admin = auth(client, "admin", "ChangeMe-Admin-2026!")
        suffix = uuid4().hex[:8]
        created = client.post("/api/v1/cameras", headers=admin, json={"camera_name": f"Pipeline Camera {suffix}", "source_type": "WEBCAM", "source_uri": "0", "location_name": f"Pipeline Location {suffix}", "metadata": {"pipeline_test": True}})
        assert created.status_code == 201, created.text
        camera_id = created.json()["id"]
        frame = np.zeros((240, 320, 3), dtype=np.uint8)
        annotated = annotate_frame(frame, [FaceBox(10, 20, 50, 60)])
        with SessionLocal() as db:
            camera = db.get(Camera, camera_id)
            assert camera is not None
            observation = create_camera_observation(db, camera, frame=frame, annotated_frame=annotated, detection=FaceBox(10, 20, 50, 60), frame_number=7, timestamp=datetime.now(UTC), created_by_id=None, metadata={"pipeline_test": True})
            db.commit()
            observation_id = observation.id
            assert observation.evidence_id
            assert observation.annotated_evidence_id
            assert db.query(Evidence).filter(Evidence.id == observation.annotated_evidence_id).count() == 1
        analyst = auth(client, "analyst", "ChangeMe-Analyst-2026!")
        review = client.post(f"/api/v1/cameras/observations/{observation_id}/review", headers=analyst, json={"decision": "ASSOCIATE", "associated_person_id": "ENT-DEMO-P1001", "notes": "Human-reviewed association for pipeline test"})
        assert review.status_code == 200, review.text
        assert review.json()["review_status"] == "ASSOCIATED_WITH_ENTITY"
        graph = client.get("/api/v1/graph?center_id=ENT-DEMO-P1001&depth=2", headers=analyst)
        assert graph.status_code == 200
        assert any(edge["relationship_type"] == "HUMAN_VERIFIED_OBSERVATION" and edge["target"] == observation_id for edge in graph.json()["edges"])
        audit = client.get("/api/v1/audit?action=OBSERVATION_ASSOCIATED_WITH_PERSON", headers=admin)
        assert audit.status_code == 200
        assert audit.json()
