from __future__ import annotations

from fastapi import APIRouter, Depends, Query
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..db import get_db
from ..dependencies import get_current_user
from ..models import Case, Entity, Evidence, Relationship, User
from ..schemas import SearchResponse, SearchResult
from ..services import record_audit
from .entities import normalize_name

router = APIRouter(prefix="/search", tags=["search"])


@router.get("", response_model=SearchResponse)
def unified_search(
    _: User = Depends(get_current_user),
    db: Session = Depends(get_db),
    q: str = Query(min_length=1, max_length=240),
    case_id: str | None = None,
    entity_type: str | None = None,
    status: str | None = None,
    evidence_category: str | None = None,
    relationship_type: str | None = None,
) -> SearchResponse:
    needle = normalize_name(q)
    results: list[SearchResult] = []
    entity_statement = select(Entity).where(Entity.record_state == "ACTIVE")
    if case_id:
        entity_statement = entity_statement.where(Entity.case_id == case_id)
    if entity_type:
        entity_statement = entity_statement.where(Entity.entity_type == entity_type.upper())
    if status:
        entity_statement = entity_statement.where(Entity.status == status.upper())
    for entity in db.scalars(entity_statement).all():
        haystack = [entity.name, *entity.aliases, entity.notes]
        if needle in normalize_name(" ".join(haystack)):
            results.append(SearchResult(result_type="ENTITY", id=entity.id, title=entity.name, subtitle=f"{entity.entity_type} · {', '.join(entity.aliases[:2]) or 'No aliases'}", entity_type=entity.entity_type, case_id=entity.case_id, status=entity.status))
    case_statement = select(Case)
    if case_id:
        case_statement = case_statement.where(Case.id == case_id)
    for case in db.scalars(case_statement).all():
        if needle in normalize_name(f"{case.case_number} {case.title} {case.description}"):
            results.append(SearchResult(result_type="CASE", id=case.id, title=case.title, subtitle=case.case_number, case_id=case.id, status=case.status))
    evidence_statement = select(Evidence)
    if case_id:
        evidence_statement = evidence_statement.where(Evidence.case_id == case_id)
    if evidence_category:
        evidence_statement = evidence_statement.where(Evidence.category == evidence_category.upper())
    for evidence in db.scalars(evidence_statement).all():
        if needle in normalize_name(f"{evidence.title} {evidence.original_filename} {evidence.extracted_text[:1000]}"):
            results.append(SearchResult(result_type="EVIDENCE", id=evidence.id, title=evidence.title, subtitle=f"{evidence.category} · {evidence.original_filename}", case_id=evidence.case_id, status=evidence.status))
    if relationship_type:
        allowed_relationship_ids = {item.id for item in db.scalars(select(Relationship).where(Relationship.relationship_type == relationship_type.upper())).all()}
        results = [item for item in results if item.result_type != "ENTITY" or item.id in {relationship.source_id for relationship in db.scalars(select(Relationship).where(Relationship.relationship_type == relationship_type.upper())).all()} | {relationship.target_id for relationship in db.scalars(select(Relationship).where(Relationship.relationship_type == relationship_type.upper())).all()}]
    results.sort(key=lambda item: (item.result_type, item.title.casefold()))
    record_audit(db, action="SEARCH_PERFORMED", user_id=_.id, details={"query": q[:500], "result_count": len(results), "filters": {"case_id": case_id, "entity_type": entity_type, "status": status, "evidence_category": evidence_category, "relationship_type": relationship_type}})
    db.commit()
    return SearchResponse(query=q, results=results[:100], total=len(results), explanation="Search results are stored records and source references. Review evidence and record state before drawing conclusions.")
