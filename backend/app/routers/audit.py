from __future__ import annotations

from fastapi import APIRouter, Depends, Query
from fastapi.responses import PlainTextResponse
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from ..db import get_db
from ..dependencies import require_roles
from ..models import AuditLog, User
from ..schemas import AuditOut

router = APIRouter(prefix="/audit", tags=["audit"])


@router.get("", response_model=list[AuditOut])
def list_audit_events(
    _: User = Depends(require_roles("ADMIN", "AUDITOR")),
    db: Session = Depends(get_db),
    action: str | None = Query(default=None, max_length=64),
    resource_type: str | None = Query(default=None, max_length=64),
    user_id: str | None = None,
    limit: int = Query(default=100, ge=1, le=500),
) -> list[AuditOut]:
    statement = select(AuditLog).options(selectinload(AuditLog.user)).order_by(AuditLog.created_at.desc()).limit(limit)
    if action:
        statement = statement.where(AuditLog.action == action.upper())
    if resource_type:
        statement = statement.where(AuditLog.resource_type == resource_type)
    if user_id:
        statement = statement.where(AuditLog.user_id == user_id)
    return [AuditOut.model_validate(event) for event in db.scalars(statement).all()]


@router.get("/export", response_class=PlainTextResponse)
def export_audit_events(
    _: User = Depends(require_roles("ADMIN", "AUDITOR")),
    db: Session = Depends(get_db),
    limit: int = Query(default=1000, ge=1, le=10000),
) -> PlainTextResponse:
    events = db.scalars(select(AuditLog).order_by(AuditLog.created_at.desc()).limit(limit)).all()
    lines = ["timestamp,action,resource_type,resource_id,user_id,details"]
    for event in events:
        details = str(event.details_json or {}).replace('"', "'").replace("\n", " ")
        lines.append(f"{event.created_at.isoformat()},{event.action},{event.resource_type or ''},{event.resource_id or ''},{event.user_id or ''},\"{details}\"")
    return PlainTextResponse("\n".join(lines), media_type="text/csv", headers={"Content-Disposition": "attachment; filename=signal-atlas-audit.csv"})
