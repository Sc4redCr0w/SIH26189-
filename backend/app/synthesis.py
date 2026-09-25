from __future__ import annotations

from collections import Counter, defaultdict
from datetime import UTC, datetime

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from .models import Case, Entity, Evidence, Relationship, Report, User


def synthesize_case(db: Session, case: Case, user: User, title: str) -> Report:
    entities = db.scalars(select(Entity).where(Entity.case_id == case.id, Entity.record_state == "ACTIVE")).all()
    relationships = db.scalars(select(Relationship).where(Relationship.case_id == case.id, Relationship.record_state != "ARCHIVED")).all()
    evidence = db.scalars(select(Evidence).where(Evidence.case_id == case.id)).all()
    type_counts = Counter(entity.entity_type for entity in entities)
    degree: dict[str, int] = defaultdict(int)
    for relationship in relationships:
        degree[relationship.source_id] += 1
        degree[relationship.target_id] += 1
    top_entities = sorted(entities, key=lambda entity: degree[entity.id], reverse=True)[:8]
    dated = [relationship for relationship in relationships if relationship.timestamp]
    date_span = f"{min(item.timestamp for item in dated).date()} to {max(item.timestamp for item in dated).date()}" if dated else "No dated relationships stored"
    evidence_ids = list(dict.fromkeys(item.id for item in evidence))
    agents = [
        {"agent": "Demographic analyst", "status": "complete", "finding": f"{len(entities)} active entities across {len(type_counts)} recorded types: {', '.join(f'{key} ({value})' for key, value in type_counts.items()) or 'none'}."},
        {"agent": "Temporal analyst", "status": "complete", "finding": f"Observed relationship date span: {date_span}."},
        {"agent": "Geographic analyst", "status": "complete", "finding": f"{sum(1 for entity in entities if entity.entity_type == 'LOCATION')} location entities have explicit map context; coordinates are not inferred."},
        {"agent": "Network analyst", "status": "complete", "finding": f"{len(relationships)} active relationships; highest direct-connectivity records: {', '.join(entity.name for entity in top_entities) or 'none'}."},
        {"agent": "Evidence/source analyst", "status": "complete", "finding": f"{len(evidence)} source records and {len(evidence_ids)} unique evidence references are available for traceability."},
    ]
    sections = [
        {"title": "Case overview", "body": f"{case.title} ({case.case_number}) is a {case.status.lower()} investigation context with {len(entities)} active entities and {len(relationships)} active relationships."},
        {"title": "Key entities", "body": ", ".join(f"{entity.name} ({entity.entity_type})" for entity in top_entities) or "No active entities stored."},
        {"title": "Network structure", "body": "The network summary is derived from stored relationship records. High-connectivity records are structural signals and require analyst review."},
        {"title": "Temporal findings", "body": f"The observed relationship window is {date_span}."},
        {"title": "Geographic findings", "body": "Location findings are limited to explicit entity metadata and evidence-backed relationships."},
        {"title": "Supporting evidence", "body": ", ".join(evidence_ids) or "No evidence references stored."},
        {"title": "System limitations", "body": "This synthesis is generated from stored records and deterministic analysis. It is not a legal finding, and missing evidence may change the interpretation."},
    ]
    latest_version = db.scalar(select(func.max(Report.version)).where(Report.case_id == case.id, Report.title == title.strip())) or 0
    report = Report(
        case_id=case.id,
        title=title.strip(),
        summary=f"Multi-agent synthesis for {case.case_number}.",
        content_json={"agents": agents, "sections": sections, "evidence_ids": evidence_ids, "generated_at": datetime.now(UTC).isoformat(), "grounded": True},
        version=latest_version + 1,
        created_by_id=user.id,
    )
    db.add(report)
    db.flush()
    return report
