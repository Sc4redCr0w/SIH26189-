from __future__ import annotations

import json
import re
from collections import defaultdict, deque

import httpx
from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from ..config import get_settings
from ..db import get_db
from ..dependencies import get_current_user
from ..models import Entity, Evidence, Relationship, User
from ..schemas import AssistantRequest, AssistantResponse
from ..services import record_audit
from .entities import normalize_name

router = APIRouter(prefix="/assistant", tags=["assistant"])


def _find_mentions(question: str, entities: list[Entity]) -> list[Entity]:
    normalized_question = normalize_name(question)
    exact = [entity for entity in entities if normalize_name(entity.name) in normalized_question]
    if exact:
        return exact
    tokens = [token for token in re.findall(r"[a-z0-9]+", normalized_question) if len(token) > 3]
    return [entity for entity in entities if any(token in normalize_name(entity.name) for token in tokens)][:5]


def _relationship_citations(
    relationships: list[Relationship],
    entity_by_id: dict[str, Entity],
    evidence_by_id: dict[str, Evidence],
) -> list[dict[str, object]]:
    citations: list[dict[str, object]] = []
    for relationship in relationships:
        source = entity_by_id.get(relationship.source_id)
        target = entity_by_id.get(relationship.target_id)
        if not source or not target:
            continue
        evidence = evidence_by_id.get(relationship.evidence_id) if relationship.evidence_id else None
        citations.append(
            {
                "relationship_id": relationship.id,
                "source": source.name,
                "target": target.name,
                "relationship_type": relationship.relationship_type,
                "evidence_id": relationship.evidence_id,
                "evidence_title": evidence.title if evidence else None,
                "timestamp": relationship.timestamp.isoformat() if relationship.timestamp else None,
            }
        )
    return citations


@router.post("/query", response_model=AssistantResponse)
def query_assistant(
    payload: AssistantRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> AssistantResponse:
    settings = get_settings()
    question = payload.question.strip()
    entities = db.scalars(select(Entity).where(Entity.record_state == "ACTIVE")).all()
    mentioned = _find_mentions(question, entities)
    mentioned_ids = {entity.id for entity in mentioned}
    relationships = db.scalars(
        select(Relationship)
        .options(selectinload(Relationship.evidence))
        .where(Relationship.record_state != "ARCHIVED")
    ).all()
    if payload.case_id:
        relationships = [relationship for relationship in relationships if relationship.case_id == payload.case_id]
    entity_by_id = {entity.id: entity for entity in entities}
    adjacency: dict[str, set[str]] = defaultdict(set)
    for relationship in relationships:
        adjacency[relationship.source_id].add(relationship.target_id)
        adjacency[relationship.target_id].add(relationship.source_id)

    lower_question = question.casefold()
    wants_multihop = any(term in lower_question for term in ("second-degree", "second degree", "2nd", "two-degree", "multi-hop", "how does", "what connects"))
    relevant_ids: set[str] = set()
    if wants_multihop and mentioned:
        frontier = {entity.id for entity in mentioned}
        relevant_ids = set(frontier)
        for _ in range(2):
            next_frontier: set[str] = set()
            for entity_id in frontier:
                next_frontier.update(adjacency.get(entity_id, set()))
            next_frontier -= relevant_ids
            relevant_ids.update(next_frontier)
            frontier = next_frontier
            if not frontier:
                break
    else:
        relevant_ids = mentioned_ids
    relevant = [relationship for relationship in relationships if relationship.source_id in relevant_ids or relationship.target_id in relevant_ids]
    if "evidence" in lower_question or "support" in lower_question or "source" in lower_question:
        relevant = [relationship for relationship in relevant if relationship.evidence_id]
    relevant = relevant[:30]
    evidence_ids = {relationship.evidence_id for relationship in relevant if relationship.evidence_id}
    evidence_rows = db.scalars(select(Evidence).where(Evidence.id.in_(evidence_ids))).all() if evidence_ids else []
    evidence_by_id = {item.id: item for item in evidence_rows}
    citations = _relationship_citations(relevant, entity_by_id, evidence_by_id)
    retrieved_entities = [entity for entity in entities if entity.id in relevant_ids]

    if not mentioned:
        answer = "I could not identify a stored entity in that question. Try an exact or partial entity name from the current investigation."
    elif not relevant:
        names = ", ".join(entity.name for entity in mentioned[:3])
        answer = f"I found {names} in the active graph, but no stored relationship was available to support a connection in the selected case."
    else:
        if wants_multihop:
            names = ", ".join(entity.name for entity in retrieved_entities[:12])
            answer = f"The stored graph shows a two-degree neighborhood involving: {names}. "
        else:
            answer = "The graph contains the following evidence-backed connections: "
        lines: list[str] = []
        for relationship in relevant[:10]:
            source = entity_by_id.get(relationship.source_id)
            target = entity_by_id.get(relationship.target_id)
            if not source or not target:
                continue
            evidence = evidence_by_id.get(relationship.evidence_id) if relationship.evidence_id else None
            suffix = f" Evidence: {evidence.title} ({evidence.id})." if evidence else " No evidence record is attached to this relationship."
            lines.append(f"{source.name} {relationship.relationship_type.lower()} {target.name}.{suffix}")
        answer += " ".join(lines)
        if "summarize" in lower_question:
            answer += f" The selected context contains {len(retrieved_entities)} entities and {len(relevant)} relationships."

    # Optional local LLM synthesis is deliberately downstream of retrieval. If it
    # is unavailable, the deterministic grounded answer remains the response.
    if settings.ollama_enabled and mentioned and relevant:
        context = json.dumps({"question": question, "facts": citations}, default=str)
        try:
            response = httpx.post(
                f"{settings.ollama_url.rstrip('/')}/api/chat",
                json={
                    "model": settings.ollama_model,
                    "stream": False,
                    "messages": [
                        {"role": "system", "content": "Summarize only the supplied evidence-backed facts. Do not infer guilt or invent relationships."},
                        {"role": "user", "content": context},
                    ],
                },
                timeout=8,
            )
            response.raise_for_status()
            generated = response.json().get("message", {}).get("content")
            if isinstance(generated, str) and generated.strip():
                answer = generated.strip()
        except httpx.HTTPError:
            # The deterministic answer remains available when the optional
            # local model is stopped or unreachable.
            pass

    record_audit(db, action="AI_QUERY_EXECUTED", user_id=current_user.id, resource_type="ASSISTANT", details={"question": question[:500], "grounded": bool(mentioned and relevant), "retrieved_count": len(citations)})
    db.commit()
    return AssistantResponse(
        answer=answer,
        citations=citations,
        retrieved_entities=[
            {"id": entity.id, "name": entity.name, "entity_type": entity.entity_type, "status": entity.status}
            for entity in retrieved_entities
        ],
        grounded=bool(mentioned and relevant),
        disclaimer="This assistant summarizes stored graph and evidence records. It does not establish guilt or replace analyst review.",
    )
