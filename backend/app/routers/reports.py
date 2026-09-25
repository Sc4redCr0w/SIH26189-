from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.responses import HTMLResponse, PlainTextResponse
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from ..db import get_db
from ..dependencies import get_current_user, require_roles
from ..models import Case, Entity, Evidence, Report, Relationship, User
from ..schemas import ReportCreate, ReportOut, SynthesisRequest
from ..synthesis import synthesize_case
from ..services import record_audit

router = APIRouter(prefix="/reports", tags=["reports"])


def report_to_out(report: Report) -> ReportOut:
    return ReportOut.model_validate(report)


@router.get("", response_model=list[ReportOut])
def list_reports(
    _: User = Depends(get_current_user),
    db: Session = Depends(get_db),
    case_id: str | None = None,
    limit: int = Query(default=50, ge=1, le=200),
) -> list[ReportOut]:
    statement = select(Report).order_by(Report.created_at.desc()).limit(limit)
    if case_id:
        statement = statement.where(Report.case_id == case_id)
    return [report_to_out(report) for report in db.scalars(statement).all()]


@router.get("/{report_id}/export")
def export_report(
    report_id: str,
    _: User = Depends(get_current_user),
    db: Session = Depends(get_db),
    format: str = Query(default="html", pattern="^(html|md)$"),
):
    report = db.get(Report, report_id)
    if report is None:
        raise HTTPException(status_code=404, detail="Report not found")
    sections = (report.content_json or {}).get("sections", [])
    if format == "md":
        lines = [f"# {report.title}", "", report.summary, ""]
        for section in sections:
            lines.extend([f"## {section.get('title', 'Section')}", "", str(section.get("body", "")), ""])
        return PlainTextResponse("\n".join(lines), media_type="text/markdown", headers={"Content-Disposition": f'attachment; filename="{report.id}.md"'})
    from html import escape
    body = "".join(f"<section><h2>{escape(str(section.get('title', 'Section')))}</h2><p>{escape(str(section.get('body', '')))}</p></section>" for section in sections)
    html = f"<!doctype html><html><head><meta charset='utf-8'><title>{escape(report.title)}</title><style>body{{font:16px system-ui;max-width:900px;margin:40px auto;padding:0 24px;color:#172126}}section{{border-top:1px solid #ccd8dc;padding:18px 0}}small{{color:#607078}}</style></head><body><h1>{escape(report.title)}</h1><p>{escape(report.summary)}</p>{body}<p><small>Generated from stored records. This report is not a legal finding.</small></p></body></html>"
    return HTMLResponse(html, headers={"Content-Disposition": f'attachment; filename="{report.id}.html"'})


@router.get("/{report_id}", response_model=ReportOut)
def get_report(
    report_id: str,
    _: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> ReportOut:
    report = db.get(Report, report_id)
    if report is None:
        raise HTTPException(status_code=404, detail="Report not found")
    return report_to_out(report)


@router.post("/synthesize", response_model=ReportOut, status_code=status.HTTP_201_CREATED)
def synthesize_report(
    payload: SynthesisRequest,
    current_user: User = Depends(require_roles("ADMIN", "ANALYST")),
    db: Session = Depends(get_db),
) -> ReportOut:
    case = db.get(Case, payload.case_id)
    if case is None:
        raise HTTPException(status_code=404, detail="Case not found")
    report = synthesize_case(db, case, current_user, payload.title)
    record_audit(db, action="REPORT_GENERATED", user_id=current_user.id, resource_type="REPORT", resource_id=report.id, details={"case_id": case.id, "mode": "multi_agent_synthesis"})
    db.commit()
    db.refresh(report)
    return report_to_out(report)


@router.post("", response_model=ReportOut, status_code=status.HTTP_201_CREATED)
def create_report(
    payload: ReportCreate,
    current_user: User = Depends(require_roles("ADMIN", "ANALYST")),
    db: Session = Depends(get_db),
) -> ReportOut:
    if payload.case_id and db.get(Case, payload.case_id) is None:
        raise HTTPException(status_code=404, detail="Case not found")
    entity_statement = select(Entity).where(Entity.record_state == "ACTIVE")
    relationship_statement = select(Relationship).where(Relationship.record_state != "ARCHIVED")
    if payload.case_id:
        entity_statement = entity_statement.where(Entity.case_id == payload.case_id)
        relationship_statement = relationship_statement.where(Relationship.case_id == payload.case_id)
    entities = db.scalars(entity_statement).all()
    relationships = db.scalars(relationship_statement).all()
    evidence_statement = select(Evidence)
    if payload.case_id:
        evidence_statement = evidence_statement.where(Evidence.case_id == payload.case_id)
    evidence = db.scalars(evidence_statement).all()
    evidence_ids = list(dict.fromkeys(item.evidence_id for item in relationships if item.evidence_id))
    graph_snapshot = {
        "nodes": [{"id": entity.id, "name": entity.name, "type": entity.entity_type} for entity in entities[:100]],
        "edges": [{"id": item.id, "source": item.source_id, "target": item.target_id, "type": item.relationship_type, "evidence_id": item.evidence_id} for item in relationships[:200]],
    }
    content = {
        "sections": [
            {"title": "Case overview", "body": payload.summary or "No summary supplied."},
            {"title": "Key entities", "body": ", ".join(entity.name for entity in entities[:30]) or "No active entities."},
            {"title": "Network structure", "body": f"{len(entities)} active entities and {len(relationships)} active relationships are stored for this selection."},
            {"title": "Temporal findings", "body": f"{sum(1 for item in relationships if item.timestamp)} relationships carry recorded timestamps."},
            {"title": "Geographic findings", "body": f"{sum(1 for entity in entities if entity.entity_type == 'LOCATION')} location entities are present; coordinates remain explicit-only."},
            {"title": "Supporting evidence", "body": ", ".join(evidence_ids) or "No relationship-level evidence references stored."},
            {"title": "System limitations", "body": "This prototype report is a structured summary, not a legal finding or automated conclusion."},
        ],
        "entity_count": len(entities),
        "relationship_count": len(relationships),
        "evidence_count": len(evidence),
        "graph_snapshot": graph_snapshot,
        "timeline_snapshot": [{"relationship_id": item.id, "timestamp": item.timestamp.isoformat() if item.timestamp else None} for item in relationships if item.timestamp][:200],
        "map_snapshot": [{"entity_id": entity.id, "name": entity.name, "latitude": (entity.metadata_json or {}).get("latitude"), "longitude": (entity.metadata_json or {}).get("longitude")} for entity in entities if (entity.metadata_json or {}).get("latitude") is not None],
        "generated_from": "stored graph records",
    }
    latest_version = db.scalar(select(func.max(Report.version)).where(Report.case_id == payload.case_id, Report.title == payload.title.strip())) or 0
    report = Report(
        case_id=payload.case_id,
        title=payload.title.strip(),
        summary=payload.summary.strip(),
        content_json=content,
        version=latest_version + 1,
        created_by_id=current_user.id,
    )
    db.add(report)
    db.flush()
    record_audit(db, action="REPORT_GENERATED", user_id=current_user.id, resource_type="REPORT", resource_id=report.id, details={"case_id": payload.case_id})
    db.commit()
    db.refresh(report)
    return report_to_out(report)
