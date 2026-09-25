from __future__ import annotations

from typing import Any, Protocol

from sqlalchemy import select
from sqlalchemy.orm import Session

from .config import get_settings
from .models import Entity, Relationship


class GraphStore(Protocol):
    def health(self) -> dict[str, Any]: ...
    def explore(self, *, center_id: str | None, depth: int, limit: int) -> dict[str, Any]: ...


class RelationalGraphStore:
    """SQLite/PostgreSQL graph projection used by the zero-service Windows profile."""

    def __init__(self, db: Session):
        self.db = db

    def health(self) -> dict[str, Any]:
        return {"status": "ok", "adapter": "relational", "dialect": self.db.bind.dialect.name}

    def explore(self, *, center_id: str | None, depth: int, limit: int) -> dict[str, Any]:
        entities = list(self.db.scalars(select(Entity).where(Entity.record_state == "ACTIVE").limit(limit)).all())
        relationships = list(self.db.scalars(select(Relationship).where(Relationship.record_state != "ARCHIVED").limit(limit * 4)).all())
        entity_ids = {entity.id for entity in entities}
        relationships = [item for item in relationships if item.source_id in entity_ids and item.target_id in entity_ids]
        if center_id:
            if center_id not in entity_ids:
                raise ValueError("Center entity not found")
            adjacency: dict[str, set[str]] = {}
            for relationship in relationships:
                adjacency.setdefault(relationship.source_id, set()).add(relationship.target_id)
                adjacency.setdefault(relationship.target_id, set()).add(relationship.source_id)
            reachable = {center_id}
            frontier = {center_id}
            for _ in range(depth):
                next_frontier = set()
                for current in frontier:
                    next_frontier.update(adjacency.get(current, set()))
                next_frontier -= reachable
                reachable.update(next_frontier)
                frontier = next_frontier
                if not frontier:
                    break
            entities = [item for item in entities if item.id in reachable]
            relationships = [item for item in relationships if item.source_id in reachable and item.target_id in reachable]
        return {
            "nodes": [
                {"id": item.id, "name": item.name, "entity_type": item.entity_type, "status": item.status, "record_state": item.record_state, "aliases": item.aliases, "case_id": item.case_id}
                for item in entities
            ],
            "edges": [
                {"id": item.id, "source": item.source_id, "target": item.target_id, "relationship_type": item.relationship_type, "confidence": item.confidence, "timestamp": item.timestamp, "evidence_id": item.evidence_id, "case_id": item.case_id, "record_state": item.record_state}
                for item in relationships
            ],
            "depth": depth,
            "center_id": center_id,
        }


class Neo4jGraphStore:
    """Optional Neo4j adapter. It is imported lazily so local Windows setup stays service-free."""

    def __init__(self) -> None:
        settings = get_settings()
        if not settings.neo4j_enabled:
            raise RuntimeError("Neo4j is disabled")
        try:
            from neo4j import GraphDatabase  # type: ignore[import-not-found]
        except ImportError as exc:  # pragma: no cover - optional dependency path
            raise RuntimeError("Install the optional neo4j package before enabling Neo4j") from exc
        self._driver = GraphDatabase.driver(settings.neo4j_uri, auth=(settings.neo4j_user, settings.neo4j_password))

    def health(self) -> dict[str, Any]:
        with self._driver.verify_connectivity() as result:
            return {"status": "ok", "adapter": "neo4j", "server": result.server_info.address}

    def explore(self, *, center_id: str | None, depth: int, limit: int) -> dict[str, Any]:  # pragma: no cover - requires service
        query = "MATCH (n:Entity)-[r:RELATES_TO]-(m:Entity) RETURN n, r, m LIMIT $limit"
        with self._driver.session() as session:
            rows = session.run(query, limit=limit).data()
        return {"nodes": [], "edges": [], "depth": depth, "center_id": center_id, "rows": rows}

    def close(self) -> None:  # pragma: no cover - optional dependency path
        self._driver.close()
