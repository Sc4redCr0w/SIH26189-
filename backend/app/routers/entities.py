from __future__ import annotations

import re
import unicodedata
from difflib import SequenceMatcher
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from sqlalchemy import delete, insert, or_, select
from sqlalchemy.orm import Session, selectinload

from ..db import get_db
from ..dependencies import get_current_user, require_roles
from ..models import Case, Entity, Evidence, ExtractionCandidate, Relationship, User, entity_evidence
from ..schemas import DuplicateMatch, EntityCreate, EntityMerge, EntityOut, EntityUpdate, EvidenceOut
from ..services import record_audit

router = APIRouter(prefix="/entities", tags=["entities"])


def normalize_name(value: str) -> str:
    normalized = unicodedata.normalize("NFKD", value).encode("ascii", "ignore").decode("ascii")
    return re.sub(r"\s+", " ", normalized.strip().casefold())


def entity_to_out(entity: Entity) -> EntityOut:
    return EntityOut.model_validate(entity)


def find_entity(db: Session, entity_id: str) -> Entity | None:
    return db.scalar(
        select(Entity)
        .options(selectinload(Entity.outgoing_relationships), selectinload(Entity.incoming_relationships))
        .where(Entity.id == entity_id)
    )


def ensure_case(db: Session, case_id: str | None) -> None:
    if case_id and db.get(Case, case_id) is None:
        raise HTTPException(status_code=404, detail="Case not found")


def duplicate_candidates(db: Session, entity: Entity, threshold: float = 0.72) -> list[DuplicateMatch]:
    candidates = db.scalars(
        select(Entity).where(
            Entity.id != entity.id,
            Entity.record_state == "ACTIVE",
            Entity.entity_type == entity.entity_type,
        )
    ).all()
    matches: list[DuplicateMatch] = []
    for candidate in candidates:
        name_score = SequenceMatcher(None, entity.normalized_name, candidate.normalized_name).ratio()
        alias_scores = [SequenceMatcher(None, entity.normalized_name, normalize_name(alias)).ratio() for alias in candidate.aliases]
        alias_scores += [SequenceMatcher(None, normalize_name(alias), candidate.normalized_name).ratio() for alias in entity.aliases]
        best_alias = max(alias_scores, default=0.0)
        shared_metadata = set(entity.metadata_json or {}).intersection(candidate.metadata_json or {})
        metadata_bonus = min(len(shared_metadata) * 0.08, 0.16)
        score = min(1.0, max(name_score, best_alias) + metadata_bonus)
        if score < threshold:
            continue
        signals = ["name similarity"] if name_score >= threshold else []
        if best_alias >= threshold:
            signals.append("alias similarity")
        if shared_metadata:
            signals.append("shared structured identifier")
        matches.append(
            DuplicateMatch(
                entity_id=candidate.id,
                name=candidate.name,
                entity_type=candidate.entity_type,
                score=round(score, 3),
                signals=signals,
                recommendation="Review manually; do not merge automatically.",
            )
        )
    return sorted(matches, key=lambda item: item.score, reverse=True)


@router.get("", response_model=list[EntityOut])
def list_entities(
    _: User = Depends(get_current_user),
    db: Session = Depends(get_db),
    q: str | None = Query(default=None, max_length=240),
    entity_type: str | None = Query(default=None, max_length=32),
    status_filter: str | None = Query(default=None, alias="status", max_length=40),
    include_archived: bool = False,
    limit: int = Query(default=100, ge=1, le=500),
) -> list[EntityOut]:
    statement = select(Entity).order_by(Entity.updated_at.desc())
    if not include_archived:
        statement = statement.where(Entity.record_state == "ACTIVE")
    if entity_type:
        statement = statement.where(Entity.entity_type == entity_type.strip().upper())
    if status_filter:
        statement = statement.where(Entity.status == status_filter.strip().upper())
    entities = db.scalars(statement.limit(limit * 3 if q else limit)).all()
    if q:
        needle = normalize_name(q)
        entities = [
            entity
            for entity in entities
            if needle in normalize_name(entity.name)
            or any(needle in normalize_name(alias) for alias in entity.aliases)
        ][:limit]
    return [entity_to_out(entity) for entity in entities]


@router.get("/search", response_model=list[EntityOut])
def search_entities(
    _: User = Depends(get_current_user),
    db: Session = Depends(get_db),
    q: str = Query(min_length=1, max_length=240),
    limit: int = Query(default=25, ge=1, le=100),
) -> list[EntityOut]:
    return list_entities(_, db, q=q, limit=limit)


@router.get("/{entity_id}/duplicates", response_model=list[DuplicateMatch])
def get_duplicate_candidates(
    entity_id: str,
    _: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> list[DuplicateMatch]:
    entity = db.get(Entity, entity_id)
    if entity is None or entity.record_state == "ARCHIVED":
        raise HTTPException(status_code=404, detail="Entity not found")
    return duplicate_candidates(db, entity)


@router.get("/{entity_id}/evidence", response_model=list[EvidenceOut])
def linked_evidence(
    entity_id: str,
    _: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> list[EvidenceOut]:
    if db.get(Entity, entity_id) is None:
        raise HTTPException(status_code=404, detail="Entity not found")
    links = db.scalars(select(entity_evidence).where(entity_evidence.entity_id == entity_id)).all()
    evidence = db.scalars(select(Evidence).where(Evidence.id.in_([link.evidence_id for link in links]))).all() if links else []
    return [EvidenceOut.model_validate(item) for item in evidence]


@router.get("/{entity_id}", response_model=EntityOut)
def get_entity(
    entity_id: str,
    _: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> EntityOut:
    entity = db.get(Entity, entity_id)
    if entity is None or entity.record_state == "ARCHIVED":
        raise HTTPException(status_code=404, detail="Entity not found")
    return entity_to_out(entity)


@router.post("", response_model=EntityOut, status_code=status.HTTP_201_CREATED)
def create_entity(
    payload: EntityCreate,
    current_user: User = Depends(require_roles("ADMIN")),
    db: Session = Depends(get_db),
) -> EntityOut:
    ensure_case(db, payload.case_id)
    normalized = normalize_name(payload.name)
    if not normalized:
        raise HTTPException(status_code=422, detail="Name must contain letters or numbers")
    entity = Entity(
        name=payload.name.strip(),
        normalized_name=normalized,
        entity_type=payload.entity_type.strip().upper(),
        aliases=payload.aliases,
        status=payload.status.strip().upper() or "UNKNOWN",
        notes=payload.notes.strip(),
        metadata_json=payload.metadata,
        case_id=payload.case_id,
        created_by_id=current_user.id,
    )
    db.add(entity)
    db.flush()
    record_audit(
        db,
        action="ENTITY_CREATED",
        user_id=current_user.id,
        resource_type="ENTITY",
        resource_id=entity.id,
        details={"name": entity.name, "entity_type": entity.entity_type},
    )
    db.commit()
    db.refresh(entity)
    return entity_to_out(entity)


@router.patch("/{entity_id}", response_model=EntityOut)
def update_entity(
    entity_id: str,
    payload: EntityUpdate,
    current_user: User = Depends(require_roles("ADMIN")),
    db: Session = Depends(get_db),
) -> EntityOut:
    entity = db.get(Entity, entity_id)
    if entity is None or entity.record_state == "ARCHIVED":
        raise HTTPException(status_code=404, detail="Entity not found")
    changes: dict[str, object] = {}
    values = payload.model_dump(exclude_unset=True)
    if "name" in values and values["name"] is not None:
        entity.name = values["name"].strip()
        entity.normalized_name = normalize_name(entity.name)
        changes["name"] = entity.name
    if "entity_type" in values and values["entity_type"] is not None:
        entity.entity_type = values["entity_type"].strip().upper()
        changes["entity_type"] = entity.entity_type
    if "aliases" in values and values["aliases"] is not None:
        entity.aliases = values["aliases"]
        changes["aliases"] = entity.aliases
    if "status" in values and values["status"] is not None:
        entity.status = values["status"].strip().upper()
        changes["status"] = entity.status
    if "notes" in values and values["notes"] is not None:
        entity.notes = values["notes"].strip()
        changes["notes"] = entity.notes
    if "metadata" in values and values["metadata"] is not None:
        entity.metadata_json = values["metadata"]
        changes["metadata"] = "updated"
    if "case_id" in values:
        ensure_case(db, values["case_id"])
        entity.case_id = values["case_id"]
        changes["case_id"] = entity.case_id
    record_audit(db, action="ENTITY_UPDATED", user_id=current_user.id, resource_type="ENTITY", resource_id=entity.id, details=changes)
    db.commit()
    db.refresh(entity)
    return entity_to_out(entity)


@router.post("/{entity_id}/merge")
def merge_entity(
    entity_id: str,
    payload: EntityMerge,
    current_user: User = Depends(require_roles("ADMIN")),
    db: Session = Depends(get_db),
) -> dict[str, object]:
    if not payload.confirm:
        raise HTTPException(status_code=409, detail="Merge requires an explicit confirmation flag")
    if entity_id == payload.target_entity_id:
        raise HTTPException(status_code=422, detail="An entity cannot be merged into itself")
    source = db.get(Entity, entity_id)
    target = db.get(Entity, payload.target_entity_id)
    if source is None or target is None or source.record_state == "ARCHIVED" or target.record_state == "ARCHIVED":
        raise HTTPException(status_code=404, detail="Both active entities are required for a merge")
    if source.entity_type != target.entity_type:
        raise HTTPException(status_code=422, detail="Entities with different types cannot be merged automatically")

    relationships = db.scalars(select(Relationship).where(or_(Relationship.source_id == source.id, Relationship.target_id == source.id))).all()
    moved_relationships = 0
    archived_relationships = 0
    for relationship in relationships:
        if relationship.record_state == "ARCHIVED":
            continue
        if relationship.source_id == source.id:
            relationship.source_id = target.id
        if relationship.target_id == source.id:
            relationship.target_id = target.id
        if relationship.source_id == relationship.target_id:
            relationship.record_state = "ARCHIVED"
            archived_relationships += 1
        else:
            moved_relationships += 1

    links = db.scalars(select(entity_evidence).where(entity_evidence.entity_id == source.id)).all()
    for link in links:
        existing = db.scalar(select(entity_evidence).where(entity_evidence.entity_id == target.id, entity_evidence.evidence_id == link.evidence_id))
        if existing is None:
            db.execute(insert(entity_evidence).values(entity_id=target.id, evidence_id=link.evidence_id, relation=link.relation))
    db.execute(delete(entity_evidence).where(entity_evidence.entity_id == source.id))

    target.aliases = list(dict.fromkeys([*target.aliases, *source.aliases]))
    target.metadata_json = {**(source.metadata_json or {}), **(target.metadata_json or {}), "merged_from": [*((target.metadata_json or {}).get("merged_from", [])), source.id]}
    if not target.case_id:
        target.case_id = source.case_id
    if source.notes and source.notes not in target.notes:
        target.notes = (target.notes + "\n\n[Merged record note] " + source.notes).strip()
    for candidate in db.scalars(select(ExtractionCandidate).where(ExtractionCandidate.entity_id == source.id)).all():
        candidate.entity_id = target.id
    source.record_state = "ARCHIVED"
    source.metadata_json = {**(source.metadata_json or {}), "merged_into_id": target.id, "merge_reason": payload.reason.strip()}
    record_audit(db, action="ENTITY_MERGED", user_id=current_user.id, resource_type="ENTITY", resource_id=target.id, details={"source_entity_id": source.id, "reason": payload.reason.strip(), "moved_relationships": moved_relationships, "archived_relationships": archived_relationships})
    db.commit()
    db.refresh(target)
    return {"entity": entity_to_out(target), "archived_entity_id": source.id, "moved_relationships": moved_relationships, "archived_relationships": archived_relationships}


@router.delete("/{entity_id}", status_code=status.HTTP_204_NO_CONTENT, response_class=Response, response_model=None)
def archive_entity(
    entity_id: str,
    current_user: User = Depends(require_roles("ADMIN")),
    db: Session = Depends(get_db),
) -> None:
    entity = db.get(Entity, entity_id)
    if entity is None or entity.record_state == "ARCHIVED":
        raise HTTPException(status_code=404, detail="Entity not found")
    entity.record_state = "ARCHIVED"
    record_audit(db, action="ENTITY_ARCHIVED", user_id=current_user.id, resource_type="ENTITY", resource_id=entity.id)
    db.commit()


@router.get("/{entity_id}/connections")
def entity_connections(
    entity_id: str,
    _: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict[str, object]:
    entity = find_entity(db, entity_id)
    if entity is None or entity.record_state == "ARCHIVED":
        raise HTTPException(status_code=404, detail="Entity not found")
    connections: list[dict[str, object]] = []
    for relationship in [*entity.outgoing_relationships, *entity.incoming_relationships]:
        if relationship.record_state == "ARCHIVED":
            continue
        other = relationship.target_entity if relationship.source_id == entity_id else relationship.source_entity
        connections.append(
            {
                "relationship_id": relationship.id,
                "relationship_type": relationship.relationship_type,
                "direction": "outgoing" if relationship.source_id == entity_id else "incoming",
                "entity": {"id": other.id, "name": other.name, "entity_type": other.entity_type},
                "confidence": relationship.confidence,
                "evidence_id": relationship.evidence_id,
            }
        )
    return {"entity_id": entity_id, "connections": connections}
