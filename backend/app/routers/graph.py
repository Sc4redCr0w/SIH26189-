from __future__ import annotations

from collections import defaultdict, deque
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from ..db import get_db
from ..dependencies import get_current_user
from ..models import Entity, Relationship, User
from ..schemas import GraphEdge, GraphNode, GraphResponse

router = APIRouter(prefix="/graph", tags=["graph"])


@router.get("", response_model=GraphResponse)
def explore_graph(
    _: User = Depends(get_current_user),
    db: Session = Depends(get_db),
    center_id: str | None = None,
    depth: int = Query(default=2, ge=1, le=5),
    relationship_types: str | None = Query(default=None, description="Comma-separated relationship types"),
    entity_types: str | None = Query(default=None, description="Comma-separated entity types"),
    case_id: str | None = None,
    start_date: datetime | None = Query(default=None, description="Only relationships at or after this time"),
    end_date: datetime | None = Query(default=None, description="Only relationships at or before this time"),
    limit: int = Query(default=150, ge=1, le=500),
) -> GraphResponse:
    entity_statement = select(Entity).where(Entity.record_state == "ACTIVE").order_by(Entity.updated_at.desc())
    if entity_types:
        allowed_types = {item.strip().upper() for item in entity_types.split(",") if item.strip()}
        entity_statement = entity_statement.where(Entity.entity_type.in_(allowed_types))
    if case_id:
        entity_statement = entity_statement.where(Entity.case_id == case_id)
    if center_id:
        # A center-based graph must not depend on an arbitrary LIMIT page.
        # Read the filtered active set, then bound the rendered result after
        # traversal so the requested entity and its neighbors remain visible.
        entities = db.scalars(entity_statement).all()
    else:
        entities = db.scalars(entity_statement.limit(limit)).all()
    entity_by_id = {entity.id: entity for entity in entities}
    if not entities:
        return GraphResponse(nodes=[], edges=[], depth=depth, center_id=center_id)

    relationship_statement = (
        select(Relationship)
        .options(selectinload(Relationship.evidence))
        .where(Relationship.record_state != "ARCHIVED")
    )
    if relationship_types:
        allowed_relationships = {item.strip().upper() for item in relationship_types.split(",") if item.strip()}
        relationship_statement = relationship_statement.where(Relationship.relationship_type.in_(allowed_relationships))
    if case_id:
        relationship_statement = relationship_statement.where(Relationship.case_id == case_id)
    if start_date:
        relationship_statement = relationship_statement.where(Relationship.timestamp >= start_date)
    if end_date:
        relationship_statement = relationship_statement.where(Relationship.timestamp <= end_date)
    relationships = db.scalars(relationship_statement).all()
    relationships = [item for item in relationships if item.source_id in entity_by_id and item.target_id in entity_by_id]

    if center_id:
        if center_id not in entity_by_id:
            raise HTTPException(status_code=404, detail="Center entity not found")
        adjacency: dict[str, set[str]] = defaultdict(set)
        for relationship in relationships:
            adjacency[relationship.source_id].add(relationship.target_id)
            adjacency[relationship.target_id].add(relationship.source_id)
        reachable = {center_id}
        queue = deque([(center_id, 0)])
        while queue:
            current, current_depth = queue.popleft()
            if current_depth >= depth:
                continue
            for neighbor in adjacency[current]:
                if neighbor not in reachable:
                    reachable.add(neighbor)
                    queue.append((neighbor, current_depth + 1))
        selected_ids = reachable
    else:
        selected_ids = set(entity_by_id)

    selected_entities = [entity for entity in entities if entity.id in selected_ids]
    if len(selected_entities) > limit:
        if center_id:
            center_entity = next((entity for entity in selected_entities if entity.id == center_id), None)
            selected_entities = ([center_entity] if center_entity else []) + [entity for entity in selected_entities if entity.id != center_id][: max(0, limit - 1)]
            selected_ids = {entity.id for entity in selected_entities}
        else:
            selected_entities = selected_entities[:limit]
            selected_ids = {entity.id for entity in selected_entities}
    selected_relationships = [item for item in relationships if item.source_id in selected_ids and item.target_id in selected_ids]
    degree: dict[str, int] = defaultdict(int)
    for relationship in selected_relationships:
        degree[relationship.source_id] += 1
        degree[relationship.target_id] += 1
    nodes = [
        GraphNode(
            id=entity.id,
            name=entity.name,
            entity_type=entity.entity_type,
            status=entity.status,
            record_state=entity.record_state,
            degree=degree[entity.id],
            aliases=entity.aliases,
            case_id=entity.case_id,
        )
        for entity in selected_entities
    ]
    edges = [
        GraphEdge(
            id=relationship.id,
            source=relationship.source_id,
            target=relationship.target_id,
            relationship_type=relationship.relationship_type,
            confidence=relationship.confidence,
            timestamp=relationship.timestamp,
            evidence_id=relationship.evidence_id,
            case_id=relationship.case_id,
            record_state=relationship.record_state,
        )
        for relationship in selected_relationships
    ]
    return GraphResponse(nodes=nodes, edges=edges, depth=depth, center_id=center_id)
