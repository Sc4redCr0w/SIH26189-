from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from .models import Camera, CameraObservation, Entity, Relationship, new_id
from .repositories import normalize_name


def _entity(db: Session, entity_id: str) -> Entity | None:
    return db.scalar(select(Entity).where(Entity.id == entity_id, Entity.record_state == "ACTIVE"))


def _ensure_relationship(
    db: Session,
    *,
    source_id: str,
    target_id: str,
    relationship_type: str,
    evidence_id: str | None,
    case_id: str | None,
    created_by_id: str | None,
    notes: str,
) -> Relationship:
    existing = db.scalar(
        select(Relationship).where(
            Relationship.source_id == source_id,
            Relationship.target_id == target_id,
            Relationship.relationship_type == relationship_type,
            Relationship.record_state != "ARCHIVED",
        )
    )
    if existing:
        return existing
    relationship = Relationship(
        source_id=source_id,
        target_id=target_id,
        relationship_type=relationship_type,
        evidence_id=evidence_id,
        case_id=case_id,
        confidence=1.0,
        notes=notes,
        created_by_id=created_by_id,
    )
    db.add(relationship)
    db.flush()
    return relationship


def ensure_camera_graph_entities(db: Session, camera: Camera, *, actor_id: str | None = None) -> tuple[Entity, Entity | None]:
    """Project a camera and its location into the existing relational graph."""
    location: Entity | None = None
    if camera.location_id:
        location = _entity(db, camera.location_id)
    if location is None and camera.location_name.strip():
        location = db.scalar(
            select(Entity).where(
                Entity.entity_type == "LOCATION",
                Entity.normalized_name == normalize_name(camera.location_name),
                Entity.record_state == "ACTIVE",
            )
        )
        if location is None:
            location = Entity(
                id=new_id("LOC"),
                name=camera.location_name.strip(),
                normalized_name=normalize_name(camera.location_name),
                entity_type="LOCATION",
                status="UNKNOWN",
                notes="Location projected from camera configuration.",
                metadata_json={"source": "camera_configuration"},
                case_id=camera.case_id,
                created_by_id=actor_id,
            )
            db.add(location)
            db.flush()
        camera.location_id = location.id

    camera_entity = _entity(db, camera.id)
    if camera_entity is None:
        camera_entity = Entity(
            id=camera.id,
            name=camera.camera_name,
            normalized_name=normalize_name(camera.camera_name),
            entity_type="CAMERA",
            status="UNKNOWN",
            notes="Camera source projected into the investigation graph.",
            metadata_json={
                "source_type": camera.source_type,
                "location_name": camera.location_name,
                "enabled": camera.enabled,
                "camera_reference_only": True,
            },
            case_id=camera.case_id,
            created_by_id=actor_id,
        )
        db.add(camera_entity)
        db.flush()
    else:
        camera_entity.name = camera.camera_name
        camera_entity.normalized_name = normalize_name(camera.camera_name)
        camera_entity.metadata_json = {**(camera_entity.metadata_json or {}), "source_type": camera.source_type, "enabled": camera.enabled}
    return camera_entity, location


def ensure_observation_graph_node(
    db: Session,
    observation: CameraObservation,
    camera: Camera,
    *,
    actor_id: str | None = None,
) -> Entity:
    camera_entity, location_entity = ensure_camera_graph_entities(db, camera, actor_id=actor_id)
    observation_entity = _entity(db, observation.id)
    if observation_entity is None:
        observation_entity = Entity(
            id=observation.id,
            name=f"Camera observation {observation.id}",
            normalized_name=normalize_name(f"Camera observation {observation.id}"),
            entity_type="CAMERA_OBSERVATION",
            status="ATTENTION" if observation.review_status == "PENDING_REVIEW" else "RELEVANT",
            notes="Camera observation. Identity association requires human review.",
            metadata_json={
                "observation_id": observation.id,
                "camera_id": camera.id,
                "review_status": observation.review_status,
                "is_simulated": observation.is_simulated,
                "detection_only": True,
                "no_biometric_matching": True,
            },
            case_id=observation.case_id or camera.case_id,
            created_by_id=actor_id,
        )
        db.add(observation_entity)
        db.flush()
    _ensure_relationship(
        db,
        source_id=observation.id,
        target_id=camera_entity.id,
        relationship_type="CAPTURED_BY",
        evidence_id=observation.evidence_id,
        case_id=observation.case_id or camera.case_id,
        created_by_id=actor_id,
        notes="Camera observation provenance; not an identity assertion.",
    )
    if location_entity:
        _ensure_relationship(
            db,
            source_id=observation.id,
            target_id=location_entity.id,
            relationship_type="LOCATED_AT",
            evidence_id=observation.evidence_id,
            case_id=observation.case_id or camera.case_id,
            created_by_id=actor_id,
            notes="Camera location provenance; not an identity assertion.",
        )
    return observation_entity


def associate_observation_with_person(
    db: Session,
    observation: CameraObservation,
    camera: Camera,
    person: Entity,
    *,
    reviewer_id: str | None,
    evidence_id: str | None,
    notes: str = "",
) -> Relationship:
    ensure_observation_graph_node(db, observation, camera, actor_id=reviewer_id)
    disclaimer = "Manually associated by an authorized human reviewer; this is a record decision, not biometric identification."
    reviewer_note = (notes or "").strip()
    relationship = _ensure_relationship(
        db,
        source_id=person.id,
        target_id=observation.id,
        relationship_type="HUMAN_VERIFIED_OBSERVATION",
        evidence_id=evidence_id or observation.annotated_evidence_id or observation.evidence_id,
        case_id=observation.case_id or camera.case_id,
        created_by_id=reviewer_id,
        notes=f"{disclaimer} Reviewer note: {reviewer_note}".strip(),
    )
    return relationship
