from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from urllib.parse import urlparse, urlunparse

from sqlalchemy.orm import Session

from .camera_detection import FaceBox
from .camera_graph import ensure_observation_graph_node
from .config import get_settings
from .models import Camera, CameraEvidence, CameraObservation, Evidence, new_id

settings = get_settings()


def mask_source_uri(source_uri: str) -> str:
    """Avoid returning credentials embedded in stream URLs to read-only clients."""
    try:
        parsed = urlparse(source_uri)
    except ValueError:
        return "configured"
    if not parsed.scheme or not parsed.netloc:
        return Path(source_uri).name or "configured"
    hostname = parsed.hostname or ""
    if parsed.port:
        hostname = f"{hostname}:{parsed.port}"
    if parsed.username or parsed.password:
        hostname = f"***@{hostname}"
    return urlunparse((parsed.scheme, hostname, parsed.path, "", "", ""))


def _write_image(frame: Any, path: Path) -> bool:
    if frame is None:
        return False
    try:
        import cv2  # type: ignore[import-not-found]

        path.parent.mkdir(parents=True, exist_ok=True)
        return bool(cv2.imwrite(str(path), frame))
    except Exception:
        return False


def _write_clip(frames: list[Any], path: Path, size: tuple[int, int]) -> bool:
    if not frames:
        return False
    try:
        import cv2  # type: ignore[import-not-found]

        path.parent.mkdir(parents=True, exist_ok=True)
        writer = cv2.VideoWriter(str(path), cv2.VideoWriter_fourcc(*"mp4v"), 5.0, size)
        if not writer.isOpened():
            return False
        for frame in frames:
            if frame is not None and getattr(frame, "shape", None):
                if (frame.shape[1], frame.shape[0]) != size:
                    frame = cv2.resize(frame, size)
                writer.write(frame)
        writer.release()
        return path.is_file()
    except Exception:
        return False


def _evidence_record(
    *,
    title: str,
    filename: str,
    path: Path,
    content_type: str,
    size: int,
    category: str,
    camera: Camera,
    case_id: str | None,
    uploaded_by_id: str | None,
    metadata: dict[str, Any],
) -> Evidence:
    return Evidence(
        title=title,
        original_filename=filename,
        stored_filename=path.name,
        content_type=content_type,
        size_bytes=size,
        category=category,
        status="PROCESSED",
        storage_path=str(path.resolve()),
        extracted_text=json.dumps(metadata, default=str),
        metadata_json=metadata,
        case_id=case_id or camera.case_id,
        uploaded_by_id=uploaded_by_id,
        processed_at=datetime.now(UTC),
    )


def create_camera_observation(
    db: Session,
    camera: Camera,
    *,
    frame: Any,
    annotated_frame: Any,
    detection: FaceBox,
    frame_number: int,
    timestamp: datetime | None = None,
    created_by_id: str | None = None,
    is_simulated: bool = False,
    simulation_label: str = "",
    suggested_person_id: str | None = None,
    metadata: dict[str, Any] | None = None,
    clip_frames: list[Any] | None = None,
) -> CameraObservation:
    """Persist one detection event and its raw/annotated evidence.

    This function never attempts identity matching. `suggested_person_id` is
    only a demo-mode hint and is not written as a graph association.
    """
    observation_id = new_id("OBS")
    observation_time = timestamp or datetime.now(UTC)
    root = settings.resolved_upload_dir.resolve() / "camera" / camera.id
    root.mkdir(parents=True, exist_ok=True)
    raw_path = root / f"{observation_id}-raw.jpg"
    annotated_path = root / f"{observation_id}-annotated.jpg"
    raw_written = _write_image(frame, raw_path)
    annotated_written = _write_image(annotated_frame, annotated_path)
    base_metadata: dict[str, Any] = {
        "camera_id": camera.id,
        "camera_name": camera.camera_name,
        "location_id": camera.location_id,
        "location_name": camera.location_name,
        "detection_only": True,
        "no_biometric_matching": True,
        "detector": "opencv-haar-frontalface",
        "bbox": detection.as_dict(),
        "frame_number": frame_number,
        "is_simulated": is_simulated,
        **(metadata or {}),
    }
    if not raw_written or not annotated_written:
        metadata_note = {"storage_error": "Frame could not be written to managed evidence storage", **base_metadata}
        evidence = _evidence_record(
            title=f"Camera observation {observation_id} (storage error)",
            filename=f"{observation_id}-storage-error.json",
            path=root / f"{observation_id}-storage-error.json",
            content_type="application/json",
            size=0,
            category="CAMERA_STORAGE_ERROR",
            camera=camera,
            case_id=camera.case_id,
            uploaded_by_id=created_by_id,
            metadata=metadata_note,
        )
        # Ensure a metadata file exists even when image encoding is unavailable.
        evidence.storage_path = str((root / f"{observation_id}-storage-error.json").resolve())
        Path(evidence.storage_path).write_text(json.dumps(metadata_note, default=str), encoding="utf-8")
        evidence.size_bytes = Path(evidence.storage_path).stat().st_size
        db.add(evidence)
        db.flush()
        observation = CameraObservation(
            id=observation_id,
            camera_id=camera.id,
            timestamp=observation_time,
            frame_number=frame_number,
            bbox_x=detection.x,
            bbox_y=detection.y,
            bbox_width=detection.width,
            bbox_height=detection.height,
            detection_confidence=detection.confidence,
            confidence_method="HAAR_CASCADE_BINARY",
            evidence_id=evidence.id,
            location_id=camera.location_id,
            location_name=camera.location_name,
            case_id=camera.case_id,
            review_status="PENDING_REVIEW",
            is_simulated=is_simulated,
            simulation_label=simulation_label,
            suggested_person_id=suggested_person_id,
            created_by_id=created_by_id,
            metadata_json=metadata_note,
        )
    else:
        raw_evidence = _evidence_record(
            title=f"Camera raw frame {observation_id}",
            filename=raw_path.name,
            path=raw_path,
            content_type="image/jpeg",
            size=raw_path.stat().st_size,
            category="CAMERA_FRAME",
            camera=camera,
            case_id=camera.case_id,
            uploaded_by_id=created_by_id,
            metadata={**base_metadata, "evidence_kind": "RAW_FRAME"},
        )
        annotated_evidence = _evidence_record(
            title=f"Camera annotated frame {observation_id}",
            filename=annotated_path.name,
            path=annotated_path,
            content_type="image/jpeg",
            size=annotated_path.stat().st_size,
            category="CAMERA_FRAME_ANNOTATED",
            camera=camera,
            case_id=camera.case_id,
            uploaded_by_id=created_by_id,
            metadata={**base_metadata, "evidence_kind": "ANNOTATED_FRAME"},
        )
        db.add_all([raw_evidence, annotated_evidence])
        db.flush()
        observation = CameraObservation(
            id=observation_id,
            camera_id=camera.id,
            timestamp=observation_time,
            frame_number=frame_number,
            bbox_x=detection.x,
            bbox_y=detection.y,
            bbox_width=detection.width,
            bbox_height=detection.height,
            detection_confidence=detection.confidence,
            confidence_method="HAAR_CASCADE_BINARY",
            evidence_id=raw_evidence.id,
            annotated_evidence_id=annotated_evidence.id,
            location_id=camera.location_id,
            location_name=camera.location_name,
            case_id=camera.case_id,
            review_status="PENDING_REVIEW",
            is_simulated=is_simulated,
            simulation_label=simulation_label,
            suggested_person_id=suggested_person_id,
            created_by_id=created_by_id,
            metadata_json=base_metadata,
        )
    db.add(observation)
    db.flush()
    db.add_all(
        [
            CameraEvidence(observation_id=observation.id, evidence_id=observation.evidence_id, kind="RAW_FRAME"),
        ]
        + ([CameraEvidence(observation_id=observation.id, evidence_id=observation.annotated_evidence_id, kind="ANNOTATED_FRAME")] if observation.annotated_evidence_id else [])
    )

    if settings.camera_evidence_clip_enabled and clip_frames and getattr(frame, "shape", None):
        clip_path = root / f"{observation_id}-clip.mp4"
        height, width = frame.shape[:2]
        if _write_clip(clip_frames, clip_path, (width, height)):
            clip_evidence = _evidence_record(
                title=f"Camera evidence clip {observation_id}",
                filename=clip_path.name,
                path=clip_path,
                content_type="video/mp4",
                size=clip_path.stat().st_size,
                category="CAMERA_CLIP",
                camera=camera,
                case_id=camera.case_id,
                uploaded_by_id=created_by_id,
                metadata={**base_metadata, "evidence_kind": "CLIP"},
            )
            db.add(clip_evidence)
            db.flush()
            observation.clip_evidence_id = clip_evidence.id
            db.add(CameraEvidence(observation_id=observation.id, evidence_id=clip_evidence.id, kind="CLIP"))

    ensure_observation_graph_node(db, observation, camera, actor_id=created_by_id)
    camera.detection_count += 1
    camera.last_detection_at = observation_time
    db.flush()
    return observation


def observation_to_dict(observation: CameraObservation, camera: Camera | None = None) -> dict[str, Any]:
    return {
        "id": observation.id,
        "camera_id": observation.camera_id,
        "camera_name": camera.camera_name if camera else "",
        "timestamp": observation.timestamp,
        "frame_number": observation.frame_number,
        "bbox": {"x": observation.bbox_x, "y": observation.bbox_y, "width": observation.bbox_width, "height": observation.bbox_height},
        "detection_confidence": observation.detection_confidence,
        "confidence_method": observation.confidence_method,
        "evidence_id": observation.evidence_id,
        "annotated_evidence_id": observation.annotated_evidence_id,
        "clip_evidence_id": observation.clip_evidence_id,
        "location_id": observation.location_id,
        "location_name": observation.location_name,
        "case_id": observation.case_id,
        "review_status": observation.review_status,
        "is_simulated": observation.is_simulated,
        "simulation_label": observation.simulation_label,
        "suggested_person_id": observation.suggested_person_id,
        "created_at": observation.created_at,
        "metadata": observation.metadata_json or {},
        "reviews": [
            {
                "id": review.id,
                "observation_id": review.observation_id,
                "reviewer_id": review.reviewer_id,
                "decision": review.decision,
                "associated_person_id": review.associated_person_id,
                "notes": review.notes,
                "reviewed_at": review.reviewed_at,
            }
            for review in observation.reviews
        ],
    }
