"""Remove camera-module test artifacts from the local development database.

Older test runs executed against the development database before test
isolation was added. This script removes only synthetic camera test rows and
leaves entities, cases, evidence, and reports untouched.

Usage:

    .\\.venv\\Scripts\\python.exe scripts\\cleanup-camera-test-data.py --yes
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))

from sqlalchemy import delete, or_, select  # noqa: E402

from app.db import SessionLocal  # noqa: E402
from app.models import (  # noqa: E402
    AuditLog,
    Camera,
    CameraEvidence,
    CameraObservation,
    Entity,
    Evidence,
    ObservationReview,
    PersonReferencePhoto,
    Relationship,
    entity_evidence,
)

TEST_NAME_MARKERS = (
    "Test Main Gate",
    "Pipeline Camera",
    "Worker Camera",
    "Reconnect Camera",
    "Permission Camera",
    "Demo Simulation Camera",
    "E2E Camera",
)


def main() -> int:
    parser = argparse.ArgumentParser(description="Clean camera test rows from the development database.")
    parser.add_argument("--yes", action="store_true", help="Apply the cleanup without confirmation.")
    args = parser.parse_args()

    db = SessionLocal()
    try:
        cameras = db.scalars(select(Camera)).all()
        targets = [camera for camera in cameras if any(marker in camera.camera_name for marker in TEST_NAME_MARKERS)]
        if not targets:
            print("No camera test artifacts found. Nothing to do.")
            return 0
        print("Cameras to remove:")
        for camera in targets:
            print(f"  - {camera.id}  {camera.camera_name}")
        if not args.yes:
            answer = input("Proceed? [y/N] ").strip().lower()
            if answer not in {"y", "yes"}:
                print("Cancelled.")
                return 1

        camera_ids = [camera.id for camera in targets]
        observation_ids = [
            observation.id
            for observation in db.scalars(select(CameraObservation).where(CameraObservation.camera_id.in_(camera_ids)))
        ]
        evidence_ids = [
            evidence.id
            for evidence in db.scalars(
                select(Evidence).where(
                    Evidence.category.in_(["CAMERA_FRAME", "CAMERA_FRAME_ANNOTATED", "CAMERA_CLIP", "CAMERA_STORAGE_ERROR"])
                )
            )
        ]
        photo_evidence_ids = [photo.evidence_id for photo in db.scalars(select(PersonReferencePhoto))]
        removable_evidence = sorted(set(evidence_ids) | set(photo_evidence_ids))

        db.execute(delete(CameraEvidence).where(CameraEvidence.observation_id.in_(observation_ids or [""])))
        db.execute(delete(ObservationReview).where(ObservationReview.observation_id.in_(observation_ids or [""])))
        db.execute(delete(PersonReferencePhoto))
        db.execute(
            delete(Relationship).where(
                or_(
                    Relationship.source_id.in_(observation_ids or [""]),
                    Relationship.target_id.in_(observation_ids or [""]),
                    Relationship.source_id.in_(camera_ids),
                    Relationship.target_id.in_(camera_ids),
                )
            )
        )
        db.execute(delete(entity_evidence).where(entity_evidence.entity_id.in_(observation_ids or [""])))
        db.execute(
            delete(Entity).where(
                or_(
                    Entity.id.in_(observation_ids or [""]),
                    Entity.id.in_(camera_ids),
                )
            )
        )
        db.execute(delete(CameraObservation).where(CameraObservation.camera_id.in_(camera_ids)))
        db.execute(delete(Camera).where(Camera.id.in_(camera_ids)))
        db.execute(
            delete(AuditLog).where(
                or_(
                    AuditLog.resource_id.in_(camera_ids),
                    AuditLog.resource_id.in_(observation_ids or [""]),
                )
            )
        )
        db.commit()

        removed_files = 0
        for evidence_id in removable_evidence:
            evidence = db.get(Evidence, evidence_id)
            if evidence is None:
                continue
            path = Path(evidence.storage_path)
            if path.is_file():
                path.unlink()
                removed_files += 1
        db.execute(delete(Evidence).where(Evidence.id.in_(removable_evidence or [""])))
        db.commit()

        print()
        print(f"Removed {len(camera_ids)} camera(s), {len(observation_ids)} observation(s), {len(removable_evidence)} evidence record(s), {removed_files} evidence file(s).")
        remaining = db.scalar(select(Camera).where(Camera.record_state == "ACTIVE"))
        print(f"Remaining active camera: {remaining.camera_name if remaining else 'none'}")
        return 0
    finally:
        db.close()


if __name__ == "__main__":
    sys.exit(main())
