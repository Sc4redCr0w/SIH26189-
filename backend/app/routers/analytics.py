from __future__ import annotations

from collections import defaultdict, deque
from datetime import UTC, date, datetime, timedelta
from statistics import mean

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from ..db import get_db
from ..dependencies import get_current_user, require_roles
from ..models import AnalysisRun, Entity, Relationship, User
from ..schemas import AnalysisMetric, AnalysisResponse, MapPoint, MapResponse, PatternSignal, SignalResponse, TimelinePoint, TimelineResponse
from ..services import record_audit

router = APIRouter(prefix="/analytics", tags=["analytics"])


def _undirected_graph(relationships: list[Relationship]) -> dict[str, set[str]]:
    graph: dict[str, set[str]] = defaultdict(set)
    for relationship in relationships:
        graph[relationship.source_id].add(relationship.target_id)
        graph[relationship.target_id].add(relationship.source_id)
    return graph


def _components(graph: dict[str, set[str]], entity_ids: list[str]) -> list[list[str]]:
    remaining = set(entity_ids)
    components: list[list[str]] = []
    while remaining:
        start = remaining.pop()
        component = [start]
        queue = deque([start])
        while queue:
            current = queue.popleft()
            for neighbor in graph.get(current, set()):
                if neighbor in remaining:
                    remaining.remove(neighbor)
                    component.append(neighbor)
                    queue.append(neighbor)
        components.append(sorted(component))
    return sorted(components, key=len, reverse=True)


def _betweenness(graph: dict[str, set[str]], entity_ids: list[str]) -> dict[str, float]:
    scores = {entity_id: 0.0 for entity_id in entity_ids}
    for source in entity_ids:
        stack: list[str] = []
        predecessors: dict[str, list[str]] = {entity_id: [] for entity_id in entity_ids}
        sigma = {entity_id: 0.0 for entity_id in entity_ids}
        distance = {entity_id: -1 for entity_id in entity_ids}
        sigma[source] = 1.0
        distance[source] = 0
        queue = deque([source])
        while queue:
            current = queue.popleft()
            stack.append(current)
            for neighbor in graph.get(current, set()):
                if neighbor not in distance:
                    distance[neighbor] = distance[current] + 1
                    queue.append(neighbor)
                if distance[neighbor] == distance[current] + 1:
                    sigma[neighbor] += sigma[current]
                    predecessors[neighbor].append(current)
        delta = {entity_id: 0.0 for entity_id in entity_ids}
        while stack:
            target = stack.pop()
            for predecessor in predecessors[target]:
                if sigma[target]:
                    delta[predecessor] += (sigma[predecessor] / sigma[target]) * (1 + delta[target])
            if target != source:
                scores[target] += delta[target]
    if len(entity_ids) > 2:
        scale = 2 / ((len(entity_ids) - 1) * (len(entity_ids) - 2))
        scores = {key: value * scale for key, value in scores.items()}
    return scores


def _pagerank(graph: dict[str, set[str]], entity_ids: list[str], iterations: int = 30) -> dict[str, float]:
    count = len(entity_ids)
    if count == 0:
        return {}
    ranks = {entity_id: 1 / count for entity_id in entity_ids}
    damping = 0.85
    for _ in range(iterations):
        updated = {entity_id: (1 - damping) / count for entity_id in entity_ids}
        for source in entity_ids:
            neighbors = graph.get(source, set())
            if not neighbors:
                share = damping * ranks[source] / count
                for entity_id in entity_ids:
                    updated[entity_id] += share
            else:
                share = damping * ranks[source] / len(neighbors)
                for neighbor in neighbors:
                    if neighbor in updated:
                        updated[neighbor] += share
        ranks = updated
    return ranks


@router.post("/network", response_model=AnalysisResponse)
def run_network_analysis(
    _: User = Depends(require_roles("ADMIN", "ANALYST", "AUDITOR")),
    db: Session = Depends(get_db),
    case_id: str | None = None,
    algorithm: str = Query(default="centrality", pattern="^(centrality|betweenness|pagerank|components)$"),
    center_id: str | None = None,
) -> AnalysisResponse:
    entity_statement = select(Entity).where(Entity.record_state == "ACTIVE")
    if case_id:
        entity_statement = entity_statement.where(Entity.case_id == case_id)
    entities = db.scalars(entity_statement).all()
    entity_by_id = {entity.id: entity for entity in entities}
    if center_id and center_id not in entity_by_id:
        raise HTTPException(status_code=404, detail="Center entity not found")
    relationship_statement = select(Relationship).where(Relationship.record_state != "ARCHIVED")
    if case_id:
        relationship_statement = relationship_statement.where(Relationship.case_id == case_id)
    relationships = [item for item in db.scalars(relationship_statement).all() if item.source_id in entity_by_id and item.target_id in entity_by_id]
    if center_id:
        graph = _undirected_graph(relationships)
        reachable = {center_id}
        queue = deque([center_id])
        while queue:
            current = queue.popleft()
            for neighbor in graph.get(current, set()):
                if neighbor not in reachable:
                    reachable.add(neighbor)
                    queue.append(neighbor)
        entity_ids = sorted(reachable)
        relationships = [item for item in relationships if item.source_id in reachable and item.target_id in reachable]
    else:
        entity_ids = list(entity_by_id)
    graph = _undirected_graph(relationships)
    components = _components(graph, entity_ids)

    if algorithm == "betweenness":
        values = _betweenness(graph, entity_ids)
        explanation = "Betweenness estimates how often an entity lies on shortest paths between other entities. It is a structural signal, not a legal conclusion."
    elif algorithm == "pagerank":
        values = _pagerank(graph, entity_ids)
        explanation = "PageRank estimates relative connectivity based on neighboring relationships. It is a structural signal, not a legal conclusion."
    elif algorithm == "components":
        values = {entity_id: float(index + 1) for index, entity_id in enumerate(entity_id for component in components for entity_id in component)}
        explanation = "Connected components identify groups with no relationship path to one another in the selected graph."
    else:
        degree = {entity_id: float(len(graph.get(entity_id, set()))) for entity_id in entity_ids}
        maximum = max(degree.values(), default=1.0)
        values = {entity_id: value / maximum if maximum else 0 for entity_id, value in degree.items()}
        explanation = "Degree centrality measures the number of direct relationships visible in the selected graph. It is a structural signal, not a legal conclusion."

    ranked = sorted(values.items(), key=lambda item: item[1], reverse=True)
    metrics = [
        AnalysisMetric(
            entity_id=entity_id,
            name=entity_by_id[entity_id].name,
            value=round(value, 6),
            rank=index + 1,
            explanation=explanation,
        )
        for index, (entity_id, value) in enumerate(ranked[:25])
    ]
    community_payload = [
        {"community_id": index + 1, "entity_ids": component, "size": len(component), "label": f"Community {index + 1}"}
        for index, component in enumerate(components)
    ]
    run = AnalysisRun(
        case_id=case_id,
        algorithm=algorithm,
        parameters_json={"center_id": center_id, "entity_count": len(entity_ids)},
        result_json={"metrics": [metric.model_dump(mode="json") for metric in metrics], "components": community_payload},
        created_by_id=_.id,
    )
    db.add(run)
    db.flush()
    record_audit(db, action="GRAPH_ANALYSIS_RUN", user_id=_.id, resource_type="ANALYSIS_RUN", resource_id=run.id, details={"algorithm": algorithm, "case_id": case_id})
    db.commit()
    db.refresh(run)
    return AnalysisResponse(
        run_id=run.id,
        algorithm=algorithm,
        metrics=metrics,
        communities=community_payload,
        component_count=len(components),
        explanation=explanation,
        created_at=run.created_at or datetime.now(UTC),
    )


@router.get("/timeline", response_model=TimelineResponse)
def build_timeline(
    _: User = Depends(get_current_user),
    db: Session = Depends(get_db),
    case_id: str | None = None,
    start_date: date | None = None,
    end_date: date | None = None,
) -> TimelineResponse:
    relationship_statement = select(Relationship).where(Relationship.record_state != "ARCHIVED", or_(Relationship.timestamp.is_not(None), Relationship.end_time.is_not(None)))
    entity_statement = select(Entity).where(Entity.record_state == "ACTIVE")
    if case_id:
        relationship_statement = relationship_statement.where(Relationship.case_id == case_id)
        entity_statement = entity_statement.where(Entity.case_id == case_id)
    if start_date:
        relationship_statement = relationship_statement.where(Relationship.timestamp >= datetime.combine(start_date, datetime.min.time(), tzinfo=UTC))
    if end_date:
        relationship_statement = relationship_statement.where(Relationship.timestamp <= datetime.combine(end_date, datetime.max.time(), tzinfo=UTC))
    relationships = db.scalars(relationship_statement).all()
    entities = db.scalars(entity_statement).all()
    if not relationships:
        return TimelineResponse(points=[], start_date=start_date.isoformat() if start_date else None, end_date=end_date.isoformat() if end_date else None, explanation="No timestamped relationships are stored for this selection.")
    dates = [item.timestamp.date() for item in relationships if item.timestamp] + [item.end_time.date() for item in relationships if item.end_time]
    first = min(dates)
    last = max(dates)
    if start_date:
        first = min(first, start_date)
    if end_date:
        last = max(last, end_date)
    buckets: dict[date, dict[str, int]] = {}
    current = first
    while current <= last:
        buckets[current] = {"relationship_count": 0, "disappearance_count": 0, "entity_count": 0, "event_count": 0}
        current += timedelta(days=1)
    for relationship in relationships:
        if relationship.timestamp:
            buckets[relationship.timestamp.date()]["relationship_count"] += 1
        if relationship.end_time:
            buckets[relationship.end_time.date()]["disappearance_count"] += 1
    for entity in entities:
        event_date = (entity.metadata_json or {}).get("event_date")
        if isinstance(event_date, str) and event_date[:10] in buckets:
            key = event_date[:10]
            buckets[date.fromisoformat(key)]["entity_count"] += 1
            if entity.entity_type == "EVENT":
                buckets[date.fromisoformat(key)]["event_count"] += 1
    cumulative = 0
    points: list[TimelinePoint] = []
    for key in sorted(buckets):
        cumulative += buckets[key]["relationship_count"]
        points.append(TimelinePoint(date=key.isoformat(), relationship_count=buckets[key]["relationship_count"], disappearance_count=buckets[key]["disappearance_count"], cumulative_relationships=cumulative, entity_count=buckets[key]["entity_count"], event_count=buckets[key]["event_count"]))
    return TimelineResponse(points=points, start_date=points[0].date if points else None, end_date=points[-1].date if points else None, explanation="Daily relationship counts show when observed links appeared in the selected graph. Counts are descriptive signals, not proof of criminal activity.")


@router.get("/geo", response_model=MapResponse)
def build_geographic_view(
    _: User = Depends(get_current_user),
    db: Session = Depends(get_db),
    case_id: str | None = None,
    start_date: datetime | None = None,
    end_date: datetime | None = None,
) -> MapResponse:
    entity_statement = select(Entity).where(Entity.record_state == "ACTIVE")
    if case_id:
        entity_statement = entity_statement.where(Entity.case_id == case_id)
    entities = db.scalars(entity_statement).all()
    relationship_statement = select(Relationship).where(Relationship.record_state != "ARCHIVED")
    if case_id:
        relationship_statement = relationship_statement.where(Relationship.case_id == case_id)
    if start_date:
        relationship_statement = relationship_statement.where(or_(Relationship.timestamp >= start_date, Relationship.start_time >= start_date))
    if end_date:
        relationship_statement = relationship_statement.where(or_(Relationship.timestamp <= end_date, Relationship.end_time <= end_date))
    relationships = db.scalars(relationship_statement).all()
    counts: dict[str, int] = defaultdict(int)
    for relationship in relationships:
        counts[relationship.source_id] += 1
        counts[relationship.target_id] += 1
    points: list[MapPoint] = []
    for entity in entities:
        metadata = entity.metadata_json or {}
        latitude = metadata.get("latitude", metadata.get("lat"))
        longitude = metadata.get("longitude", metadata.get("lng", metadata.get("lon")))
        try:
            if latitude is None or longitude is None:
                continue
            latitude = float(latitude)
            longitude = float(longitude)
        except (TypeError, ValueError):
            continue
        if not -90 <= latitude <= 90 or not -180 <= longitude <= 180:
            continue
        points.append(MapPoint(entity_id=entity.id, name=entity.name, entity_type=entity.entity_type, latitude=latitude, longitude=longitude, address=str(metadata.get("address")) if metadata.get("address") else None, relationship_count=counts[entity.id], case_id=entity.case_id))
    return MapResponse(points=points, total_relationships=len(relationships), explanation="Map points represent entities with explicit latitude/longitude metadata. Missing coordinates are not inferred from names or addresses.")


@router.post("/signals", response_model=SignalResponse)
def detect_pattern_signals(
    _: User = Depends(require_roles("ADMIN", "ANALYST", "AUDITOR")),
    db: Session = Depends(get_db),
    case_id: str | None = None,
    threshold_multiplier: float = Query(default=1.5, ge=1.0, le=5.0),
) -> SignalResponse:
    entity_statement = select(Entity).where(Entity.record_state == "ACTIVE")
    relationship_statement = select(Relationship).where(Relationship.record_state != "ARCHIVED")
    if case_id:
        entity_statement = entity_statement.where(Entity.case_id == case_id)
        relationship_statement = relationship_statement.where(Relationship.case_id == case_id)
    entities = db.scalars(entity_statement).all()
    relationships = db.scalars(relationship_statement).all()
    entity_ids = {entity.id for entity in entities}
    relationships = [item for item in relationships if item.source_id in entity_ids and item.target_id in entity_ids]
    graph = _undirected_graph(relationships)
    components = _components(graph, list(entity_ids))
    daily: dict[date, list[Relationship]] = defaultdict(list)
    for relationship in relationships:
        if relationship.timestamp:
            daily[relationship.timestamp.date()].append(relationship)
    daily_counts = [len(items) for items in daily.values()]
    average = mean(daily_counts) if daily_counts else 0.0
    maximum = max(daily_counts, default=0)
    threshold = average * threshold_multiplier
    signals: list[PatternSignal] = []
    if maximum >= 2 and maximum > threshold:
        peak_date, peak_items = max(daily.items(), key=lambda item: len(item[1]))
        signals.append(
            PatternSignal(
                signal_type="COMMUNICATION_SPIKE",
                title=f"Relationship activity spike on {peak_date.isoformat()}",
                severity="REVIEW",
                explanation=f"Observed relationship count ({maximum}) exceeds the selected baseline threshold ({threshold:.1f}) for the current case. This is a measurable change, not a conclusion about intent.",
                relationship_ids=[item.id for item in peak_items],
                evidence_ids=list(dict.fromkeys(item.evidence_id for item in peak_items if item.evidence_id)),
            )
        )
    high_degree = sorted(((entity_id, len(neighbors)) for entity_id, neighbors in graph.items()), key=lambda item: item[1], reverse=True)
    for entity_id, degree in high_degree[:3]:
        if degree < 2:
            continue
        entity = next((item for item in entities if item.id == entity_id), None)
        if not entity:
            continue
        related = [item for item in relationships if entity_id in (item.source_id, item.target_id)]
        signals.append(
            PatternSignal(
                signal_type="NETWORK_EXPANSION_OR_BRIDGE",
                title=f"High-connectivity structure: {entity.name}",
                severity="ATTENTION" if degree >= 3 else "REVIEW",
                explanation=f"The entity has {degree} direct neighbors in the selected graph. Structural prominence can indicate a coordination point, a broker, or simply an active record; analyst review is required.",
                entity_ids=[entity_id],
                relationship_ids=[item.id for item in related],
                evidence_ids=list(dict.fromkeys(item.evidence_id for item in related if item.evidence_id)),
            )
        )
    for location in [entity for entity in entities if entity.entity_type == "LOCATION"]:
        degree = len(graph.get(location.id, set()))
        if degree >= 2:
            related = [item for item in relationships if location.id in (item.source_id, item.target_id)]
            signals.append(
                PatternSignal(
                    signal_type="LOCATION_FREQUENCY",
                    title=f"Repeated location context: {location.name}",
                    severity="REVIEW",
                    explanation=f"This location is directly connected to {degree} entities in the selected graph. Frequency is a review signal, not evidence of wrongdoing by itself.",
                    entity_ids=[location.id],
                    relationship_ids=[item.id for item in related],
                )
            )
    if len(components) > 1:
        signals.append(
            PatternSignal(
                signal_type="COMMUNITY_SEPARATION",
                title=f"{len(components)} disconnected communities detected",
                severity="REVIEW",
                explanation="The selected graph contains disconnected components. Review whether the separation is meaningful or caused by missing evidence.",
                entity_ids=[component[0] for component in components if component],
            )
        )
    baseline = {
        "daily_mean": round(average, 3),
        "daily_max": maximum,
        "threshold": round(threshold, 3),
        "relationship_count": len(relationships),
        "component_count": len(components),
    }
    run = AnalysisRun(
        case_id=case_id,
        algorithm="pattern_detection",
        parameters_json={"threshold_multiplier": threshold_multiplier},
        result_json={"signals": [signal.model_dump(mode="json") for signal in signals], "baseline": baseline},
        created_by_id=_.id,
    )
    db.add(run)
    db.flush()
    record_audit(db, action="PATTERN_SIGNALS_GENERATED", user_id=_.id, resource_type="ANALYSIS_RUN", resource_id=run.id, details={"signal_count": len(signals), "case_id": case_id})
    db.commit()
    db.refresh(run)
    return SignalResponse(
        run_id=run.id,
        signals=signals,
        baseline=baseline,
        explanation="Signals are generated from measurable graph, time, and location baselines. They are prompts for analyst review and never declarations of criminality.",
        created_at=run.created_at or datetime.now(UTC),
    )
