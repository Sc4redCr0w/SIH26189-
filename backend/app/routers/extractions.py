from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from sqlalchemy import insert, select
from sqlalchemy.orm import Session

from ..db import get_db
from ..dependencies import get_current_user, require_roles
from ..extraction import extract_candidates
from ..models import Entity, Evidence, ExtractionCandidate, Relationship, User, entity_evidence
from ..schemas import CandidateOut
from ..services import record_audit
from .entities import normalize_name

router = APIRouter(tags=["extraction"])


def candidate_to_out(candidate: ExtractionCandidate) -> CandidateOut:
    return CandidateOut.model_validate(candidate)


@router.get("/extractions/candidates", response_model=list[CandidateOut])
def list_candidates(
    _: User = Depends(get_current_user),
    db: Session = Depends(get_db),
    evidence_id: str | None = None,
    candidate_type: str | None = None,
    candidate_status: str | None = Query(default=None, alias="status"),
    limit: int = Query(default=100, ge=1, le=500),
) -> list[CandidateOut]:
    statement = select(ExtractionCandidate).order_by(ExtractionCandidate.created_at.desc()).limit(limit)
    if evidence_id:
        statement = statement.where(ExtractionCandidate.evidence_id == evidence_id)
    if candidate_type:
        statement = statement.where(ExtractionCandidate.candidate_type == candidate_type.upper())
    if candidate_status:
        statement = statement.where(ExtractionCandidate.status == candidate_status.upper())
    return [candidate_to_out(item) for item in db.scalars(statement).all()]


@router.post("/evidence/{evidence_id}/extract", response_model=list[CandidateOut])
def extract_evidence_candidates(
    evidence_id: str,
    current_user: User = Depends(require_roles("ADMIN")),
    db: Session = Depends(get_db),
) -> list[CandidateOut]:
    evidence = db.get(Evidence, evidence_id)
    if evidence is None:
        raise HTTPException(status_code=404, detail="Evidence not found")
    text = evidence.extracted_text
    if not text:
        path = Path(evidence.storage_path)
        if path.is_file() and path.suffix.lower() in {".txt", ".csv"}:
            text = path.read_text(encoding="utf-8", errors="replace")
    if not text.strip():
        raise HTTPException(status_code=422, detail="No text is available for extraction; OCR or manual transcription is required")

    existing = {
        (item.candidate_type, item.normalized_value)
        for item in db.scalars(select(ExtractionCandidate).where(ExtractionCandidate.evidence_id == evidence_id)).all()
    }
    created: list[ExtractionCandidate] = []
    for value in extract_candidates(text, evidence.original_filename):
        if (value.candidate_type, value.normalized_value) in existing:
            continue
        candidate = ExtractionCandidate(
            evidence_id=evidence.id,
            candidate_type=value.candidate_type,
            value=value.value,
            normalized_value=value.normalized_value,
            confidence=value.confidence,
            source_span=value.source_span,
        )
        db.add(candidate)
        created.append(candidate)
    evidence.status = "PROCESSED"
    evidence.processed_at = datetime.now(UTC)
    record_audit(db, action="AI_EXTRACTION_EXTRACTED", user_id=current_user.id, resource_type="EVIDENCE", resource_id=evidence.id, details={"candidate_count": len(created)})
    db.commit()
    for candidate in created:
        db.refresh(candidate)
    return [candidate_to_out(item) for item in created]


def _entity_for_value(db: Session, value: str, entity_type: str, evidence: Evidence, current_user: User) -> Entity:
    normalized = normalize_name(value)
    existing = db.scalar(select(Entity).where(Entity.normalized_name == normalized, Entity.record_state == "ACTIVE"))
    if existing:
        link = db.scalar(select(entity_evidence).where(entity_evidence.entity_id == existing.id, entity_evidence.evidence_id == evidence.id))
        if link is None:
            db.execute(insert(entity_evidence).values(entity_id=existing.id, evidence_id=evidence.id, relation="MENTIONED_IN"))
        return existing
    entity = Entity(
        name=value,
        normalized_name=normalized,
        entity_type=entity_type,
        aliases=[],
        status="UNKNOWN",
        notes=f"Created from evidence candidate in {evidence.original_filename}.",
        metadata_json={"source_evidence_id": evidence.id},
        case_id=evidence.case_id,
        created_by_id=current_user.id,
    )
    db.add(entity)
    db.flush()
    db.execute(insert(entity_evidence).values(entity_id=entity.id, evidence_id=evidence.id, relation="MENTIONED_IN"))
    return entity


@router.post("/extractions/candidates/{candidate_id}/approve")
def approve_candidate(
    candidate_id: str,
    current_user: User = Depends(require_roles("ADMIN")),
    db: Session = Depends(get_db),
) -> dict[str, object]:
    candidate = db.get(ExtractionCandidate, candidate_id)
    if candidate is None:
        raise HTTPException(status_code=404, detail="Candidate not found")
    if candidate.status != "PENDING":
        raise HTTPException(status_code=409, detail="Candidate has already been reviewed")
    evidence = db.get(Evidence, candidate.evidence_id)
    if evidence is None:
        raise HTTPException(status_code=404, detail="Candidate evidence not found")

    if candidate.candidate_type == "RELATIONSHIP":
        parts = candidate.value.split("|")
        if len(parts) != 3:
            raise HTTPException(status_code=422, detail="Relationship candidate is malformed")
        source_name, relationship_type, target_name = parts
        source_type = "PERSON" if not relationship_type else "PERSON"
        target_type = "PHONE" if relationship_type == "USES" else source_type
        source = _entity_for_value(db, source_name, source_type, evidence, current_user)
        target = _entity_for_value(db, target_name, target_type, evidence, current_user)
        relationship = Relationship(
            source_id=source.id,
            target_id=target.id,
            relationship_type=relationship_type,
            evidence_id=evidence.id,
            case_id=evidence.case_id,
            confidence=candidate.confidence,
            notes=f"Approved from extraction candidate {candidate.id}.",
            created_by_id=current_user.id,
        )
        db.add(relationship)
        db.flush()
        candidate.entity_id = source.id
        candidate.status = "APPROVED"
        candidate.reviewed_by_id = current_user.id
        candidate.reviewed_at = datetime.now(UTC)
        record_audit(db, action="AI_EXTRACTION_APPROVED", user_id=current_user.id, resource_type="RELATIONSHIP", resource_id=relationship.id, details={"candidate_id": candidate.id})
        db.commit()
        return {"candidate": candidate_to_out(candidate), "relationship_id": relationship.id, "entity_ids": [source.id, target.id]}

    entity_type = candidate.candidate_type if candidate.candidate_type in {"PERSON", "PHONE", "VEHICLE", "LOCATION", "ORGANIZATION", "EVENT"} else "EVENT"
    entity = _entity_for_value(db, candidate.value, entity_type, evidence, current_user)
    candidate.entity_id = entity.id
    candidate.status = "APPROVED"
    candidate.reviewed_by_id = current_user.id
    candidate.reviewed_at = datetime.now(UTC)
    record_audit(db, action="AI_EXTRACTION_APPROVED", user_id=current_user.id, resource_type="ENTITY", resource_id=entity.id, details={"candidate_id": candidate.id, "candidate_type": candidate.candidate_type})
    db.commit()
    db.refresh(candidate)
    return {"candidate": candidate_to_out(candidate), "entity_id": entity.id}


@router.post("/extractions/candidates/{candidate_id}/reject", status_code=status.HTTP_204_NO_CONTENT, response_class=Response, response_model=None)
def reject_candidate(
    candidate_id: str,
    current_user: User = Depends(require_roles("ADMIN")),
    db: Session = Depends(get_db),
) -> None:
    candidate = db.get(ExtractionCandidate, candidate_id)
    if candidate is None:
        raise HTTPException(status_code=404, detail="Candidate not found")
    if candidate.status != "PENDING":
        raise HTTPException(status_code=409, detail="Candidate has already been reviewed")
    candidate.status = "REJECTED"
    candidate.reviewed_by_id = current_user.id
    candidate.reviewed_at = datetime.now(UTC)
    record_audit(db, action="AI_EXTRACTION_REJECTED", user_id=current_user.id, resource_type="EXTRACTION_CANDIDATE", resource_id=candidate.id)
    db.commit()
