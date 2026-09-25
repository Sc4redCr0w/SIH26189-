from __future__ import annotations

import re
import unicodedata
from collections.abc import Iterable

from sqlalchemy import select
from sqlalchemy.orm import Session

from .models import Case, Entity, Relationship


def normalize_name(value: str) -> str:
    normalized = unicodedata.normalize("NFKD", value).encode("ascii", "ignore").decode("ascii")
    return re.sub(r"\s+", " ", normalized.strip().casefold())


class EntityRepository:
    def __init__(self, db: Session):
        self.db = db

    def get(self, entity_id: str, include_archived: bool = False) -> Entity | None:
        statement = select(Entity).where(Entity.id == entity_id)
        if not include_archived:
            statement = statement.where(Entity.record_state != "ARCHIVED")
        return self.db.scalar(statement)

    def list(self, *, query: str | None = None, entity_type: str | None = None, include_archived: bool = False, limit: int = 100) -> list[Entity]:
        statement = select(Entity).order_by(Entity.updated_at.desc()).limit(limit)
        if not include_archived:
            statement = statement.where(Entity.record_state == "ACTIVE")
        if entity_type:
            statement = statement.where(Entity.entity_type == entity_type.upper())
        rows = list(self.db.scalars(statement).all())
        if query:
            needle = normalize_name(query)
            rows = [row for row in rows if needle in normalize_name(row.name) or any(needle in normalize_name(alias) for alias in row.aliases)]
        return rows

    def create(self, *, name: str, entity_type: str, aliases: Iterable[str] = (), status: str = "UNKNOWN", notes: str = "", metadata: dict | None = None, case_id: str | None = None, created_by_id: str | None = None) -> Entity:
        entity = Entity(
            name=name.strip(),
            normalized_name=normalize_name(name),
            entity_type=entity_type.strip().upper(),
            aliases=list(dict.fromkeys(alias.strip() for alias in aliases if alias.strip())),
            status=status.strip().upper() or "UNKNOWN",
            notes=notes.strip(),
            metadata_json=metadata or {},
            case_id=case_id,
            created_by_id=created_by_id,
        )
        self.db.add(entity)
        self.db.flush()
        return entity

    def archive(self, entity: Entity) -> None:
        entity.record_state = "ARCHIVED"


class RelationshipRepository:
    def __init__(self, db: Session):
        self.db = db

    def get(self, relationship_id: str, include_archived: bool = False) -> Relationship | None:
        statement = select(Relationship).where(Relationship.id == relationship_id)
        if not include_archived:
            statement = statement.where(Relationship.record_state != "ARCHIVED")
        return self.db.scalar(statement)

    def list(self, *, case_id: str | None = None, source_id: str | None = None, target_id: str | None = None, relationship_type: str | None = None, include_archived: bool = False, limit: int = 500) -> list[Relationship]:
        statement = select(Relationship).order_by(Relationship.created_at.desc()).limit(limit)
        if not include_archived:
            statement = statement.where(Relationship.record_state != "ARCHIVED")
        if case_id:
            statement = statement.where(Relationship.case_id == case_id)
        if source_id:
            statement = statement.where(Relationship.source_id == source_id)
        if target_id:
            statement = statement.where(Relationship.target_id == target_id)
        if relationship_type:
            statement = statement.where(Relationship.relationship_type == relationship_type.upper())
        return list(self.db.scalars(statement).all())

    def create(self, *, source_id: str, target_id: str, relationship_type: str, created_by_id: str | None = None, **values: object) -> Relationship:
        relationship = Relationship(
            source_id=source_id,
            target_id=target_id,
            relationship_type=relationship_type.strip().upper(),
            created_by_id=created_by_id,
            **values,
        )
        self.db.add(relationship)
        self.db.flush()
        return relationship

    def archive(self, relationship: Relationship) -> None:
        relationship.record_state = "ARCHIVED"


class CaseRepository:
    def __init__(self, db: Session):
        self.db = db

    def get(self, case_id: str) -> Case | None:
        return self.db.get(Case, case_id)

    def list(self, status: str | None = None) -> list[Case]:
        statement = select(Case).order_by(Case.updated_at.desc())
        if status:
            statement = statement.where(Case.status == status.upper())
        return list(self.db.scalars(statement).all())

    def create(self, *, case_number: str, title: str, description: str = "", status: str = "ACTIVE", priority: str = "MEDIUM", created_by_id: str | None = None) -> Case:
        case = Case(
            case_number=case_number.strip().upper(),
            title=title.strip(),
            description=description.strip(),
            status=status.upper(),
            priority=priority.upper(),
            created_by_id=created_by_id,
        )
        self.db.add(case)
        self.db.flush()
        return case
