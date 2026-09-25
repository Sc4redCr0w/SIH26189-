from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from ..db import get_db
from ..dependencies import get_current_user, require_roles
from ..models import Case, Entity, Evidence, Relationship, User
from ..schemas import CaseOut, EvidenceOut, EvidenceTrace, RelationshipCreate, RelationshipOut, RelationshipUpdate
from ..services import record_audit

router = APIRouter(prefix="/relationships", tags=["relationships"])


def relationship_to_out(relationship: Relationship) -> RelationshipOut:
    return RelationshipOut.model_validate(relationship)


def validate_references(db: Session, payload: RelationshipCreate | RelationshipUpdate) -> None:
    if "source_id" in payload.model_fields_set and payload.source_id is not None:
        if db.get(Entity, payload.source_id) is None:
            raise HTTPException(status_code=404, detail="Source entity not found")
    if "target_id" in payload.model_fields_set and payload.target_id is not None:
        if db.get(Entity, payload.target_id) is None:
            raise HTTPException(status_code=404, detail="Target entity not found")
    if "evidence_id" in payload.model_fields_set and payload.evidence_id is not None:
        if db.get(Evidence, payload.evidence_id) is None:
            raise HTTPException(status_code=404, detail="Evidence not found")
    if "case_id" in payload.model_fields_set and payload.case_id is not None:
        if db.get(Case, payload.case_id) is None:
            raise HTTPException(status_code=404, detail="Case not found")


@router.get("", response_model=list[RelationshipOut])
def list_relationships(
    _: User = Depends(get_current_user),
    db: Session = Depends(get_db),
    case_id: str | None = None,
    source_id: str | None = None,
    target_id: str | None = None,
    relationship_type: str | None = Query(default=None, max_length=48),
    include_archived: bool = False,
    limit: int = Query(default=500, ge=1, le=2000),
) -> list[RelationshipOut]:
    statement = select(Relationship).order_by(Relationship.created_at.desc())
    if not include_archived:
        statement = statement.where(Relationship.record_state != "ARCHIVED")
    if case_id:
        statement = statement.where(Relationship.case_id == case_id)
    if source_id:
        statement = statement.where(Relationship.source_id == source_id)
    if target_id:
        statement = statement.where(Relationship.target_id == target_id)
    if relationship_type:
        statement = statement.where(Relationship.relationship_type == relationship_type.strip().upper())
    return [relationship_to_out(item) for item in db.scalars(statement.limit(limit)).all()]


@router.get("/{relationship_id}", response_model=RelationshipOut)
def get_relationship(
    relationship_id: str,
    _: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> RelationshipOut:
    relationship = db.get(Relationship, relationship_id)
    if relationship is None or relationship.record_state == "ARCHIVED":
        raise HTTPException(status_code=404, detail="Relationship not found")
    return relationship_to_out(relationship)


@router.get("/{relationship_id}/trace", response_model=EvidenceTrace)
def get_relationship_trace(
    relationship_id: str,
    _: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> EvidenceTrace:
    relationship = db.get(Relationship, relationship_id)
    if relationship is None or relationship.record_state == "ARCHIVED":
        raise HTTPException(status_code=404, detail="Relationship not found")
    source = db.get(Entity, relationship.source_id)
    target = db.get(Entity, relationship.target_id)
    evidence = db.get(Evidence, relationship.evidence_id) if relationship.evidence_id else None
    case = db.get(Case, relationship.case_id) if relationship.case_id else None
    return EvidenceTrace(
        relationship=RelationshipOut.model_validate(relationship).model_dump(mode="json"),
        source={"id": source.id, "name": source.name, "entity_type": source.entity_type} if source else {"id": relationship.source_id},
        target={"id": target.id, "name": target.name, "entity_type": target.entity_type} if target else {"id": relationship.target_id},
        evidence=EvidenceOut.model_validate(evidence).model_dump(mode="json") if evidence else None,
        case=CaseOut.model_validate(case).model_dump(mode="json") if case else None,
    )


@router.post("", response_model=RelationshipOut, status_code=status.HTTP_201_CREATED)
def create_relationship(
    payload: RelationshipCreate,
    current_user: User = Depends(require_roles("ADMIN")),
    db: Session = Depends(get_db),
) -> RelationshipOut:
    if payload.source_id == payload.target_id:
        raise HTTPException(status_code=422, detail="An entity cannot relate to itself")
    validate_references(db, payload)
    relationship = Relationship(
        source_id=payload.source_id,
        target_id=payload.target_id,
        relationship_type=payload.relationship_type,
        timestamp=payload.timestamp,
        start_time=payload.start_time,
        end_time=payload.end_time,
        evidence_id=payload.evidence_id,
        case_id=payload.case_id,
        confidence=payload.confidence,
        notes=payload.notes.strip(),
        created_by_id=current_user.id,
    )
    db.add(relationship)
    db.flush()
    record_audit(
        db,
        action="RELATIONSHIP_CREATED",
        user_id=current_user.id,
        resource_type="RELATIONSHIP",
        resource_id=relationship.id,
        details={"source_id": relationship.source_id, "target_id": relationship.target_id, "type": relationship.relationship_type},
    )
    db.commit()
    db.refresh(relationship)
    return relationship_to_out(relationship)


@router.patch("/{relationship_id}", response_model=RelationshipOut)
def update_relationship(
    relationship_id: str,
    payload: RelationshipUpdate,
    current_user: User = Depends(require_roles("ADMIN")),
    db: Session = Depends(get_db),
) -> RelationshipOut:
    relationship = db.get(Relationship, relationship_id)
    if relationship is None or relationship.record_state == "ARCHIVED":
        raise HTTPException(status_code=404, detail="Relationship not found")
    validate_references(db, payload)
    values = payload.model_dump(exclude_unset=True)
    changes: dict[str, object] = {}
    for field in ("relationship_type", "timestamp", "start_time", "end_time", "evidence_id", "case_id", "confidence", "notes"):
        if field in values:
            setattr(relationship, field, values[field])
            changes[field] = values[field]
    if "relationship_type" in values and values["relationship_type"]:
        relationship.relationship_type = values["relationship_type"].strip().upper()
    record_audit(db, action="RELATIONSHIP_UPDATED", user_id=current_user.id, resource_type="RELATIONSHIP", resource_id=relationship.id, details=changes)
    db.commit()
    db.refresh(relationship)
    return relationship_to_out(relationship)


@router.delete("/{relationship_id}", status_code=status.HTTP_204_NO_CONTENT, response_class=Response, response_model=None)
def archive_relationship(
    relationship_id: str,
    current_user: User = Depends(require_roles("ADMIN")),
    db: Session = Depends(get_db),
) -> None:
    relationship = db.get(Relationship, relationship_id)
    if relationship is None or relationship.record_state == "ARCHIVED":
        raise HTTPException(status_code=404, detail="Relationship not found")
    relationship.record_state = "ARCHIVED"
    record_audit(db, action="RELATIONSHIP_ARCHIVED", user_id=current_user.id, resource_type="RELATIONSHIP", resource_id=relationship.id)
    db.commit()
