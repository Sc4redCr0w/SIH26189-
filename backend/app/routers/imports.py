from __future__ import annotations

import csv
import io
import uuid
from pathlib import Path

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile, status
from sqlalchemy import insert, select
from sqlalchemy.orm import Session

from ..config import get_settings
from ..db import get_db
from ..dependencies import require_roles
from ..models import Case, Entity, Evidence, Relationship, User, entity_evidence
from ..services import record_audit
from .entities import normalize_name

router = APIRouter(prefix="/imports", tags=["imports"])
settings = get_settings()


@router.post("/csv", status_code=status.HTTP_201_CREATED)
async def import_csv(
    current_user: User = Depends(require_roles("ADMIN")),
    db: Session = Depends(get_db),
    file: UploadFile = File(...),
    title: str = Form(...),
    category: str = Form("OTHER"),
    case_id: str | None = Form(default=None),
) -> dict[str, object]:
    filename = Path(file.filename or "import.csv").name
    if Path(filename).suffix.lower() != ".csv":
        raise HTTPException(status_code=415, detail="Only CSV imports are supported by this endpoint")
    content = await file.read(5 * 1024 * 1024 + 1)
    if len(content) > 5 * 1024 * 1024:
        raise HTTPException(status_code=413, detail="CSV exceeds the 5 MB import limit")
    try:
        text = content.decode("utf-8-sig")
    except UnicodeDecodeError as exc:
        raise HTTPException(status_code=422, detail="CSV must be UTF-8 encoded") from exc
    rows = list(csv.DictReader(io.StringIO(text)))
    if not rows:
        raise HTTPException(status_code=422, detail="CSV has no data rows")
    case = db.get(Case, case_id) if case_id else None
    if case_id and case is None:
        raise HTTPException(status_code=404, detail="Case not found")

    root = settings.resolved_upload_dir.resolve()
    root.mkdir(parents=True, exist_ok=True)
    stored_name = f"{uuid.uuid4().hex}.csv"
    path = root / stored_name
    path.write_bytes(content)
    evidence = Evidence(title=title.strip() or filename, original_filename=filename, stored_filename=stored_name, content_type="text/csv", size_bytes=len(content), category=category.upper() or "OTHER", status="PROCESSED", storage_path=str(path.resolve()), extracted_text=text[:500_000], metadata_json={"synthetic": "unknown", "row_count": len(rows)}, case_id=case_id, uploaded_by_id=current_user.id)
    db.add(evidence)
    db.flush()
    entity_count = 0
    relationship_count = 0
    entity_by_external: dict[str, Entity] = {}
    for row in rows:
        external_id = str(row.get("id") or row.get("entity_id") or row.get("person_id") or row.get("phone_id") or row.get("vehicle_id") or row.get("location_id") or row.get("organization_id") or "").strip()
        name = str(row.get("name") or row.get("full_name") or row.get("number") or row.get("registration") or "").strip()
        entity_type = str(row.get("entity_type") or row.get("type") or "PERSON").strip().upper()
        if row.get("source_id") and row.get("target_id"):
            continue
        if name.casefold() in {"name", "full_name", "source_id", "target_id", "relationship_type"} or entity_type.casefold() in {"entity_type", "type", "calls", "call", "transactions", "transaction", "events", "event", "associated_with", "owns", "uses", "visited", "works_for", "transferred_to", "present_at"}:
            continue
        if name and entity_type not in {"CALL", "TRANSACTION", "EVENT"}:
            existing = db.scalar(select(Entity).where(Entity.normalized_name == normalize_name(name), Entity.record_state == "ACTIVE"))
            if existing is None:
                existing = Entity(name=name, normalized_name=normalize_name(name), entity_type=entity_type, aliases=[], status=str(row.get("status") or "UNKNOWN").upper(), notes="Imported from CSV; verify against source evidence.", metadata_json={"import_evidence_id": evidence.id}, case_id=case_id, created_by_id=current_user.id)
                db.add(existing)
                db.flush()
                entity_count += 1
            if external_id:
                entity_by_external[external_id] = existing
            db.execute(insert(entity_evidence).values(entity_id=existing.id, evidence_id=evidence.id, relation="MENTIONED_IN"))
    for row in rows:
        source_external = str(row.get("source_id") or row.get("source") or row.get("from_account") or row.get("id") or "").strip()
        target_external = str(row.get("target_id") or row.get("target") or row.get("to_account") or row.get("name") or "").strip()
        relationship_type = str(row.get("relationship_type") or row.get("type") or (row.get("entity_type") if str(row.get("entity_type") or "").upper() in {"CALL", "CALLS", "TRANSACTION", "EVENT", "ASSOCIATED_WITH", "OWNS", "USES", "VISITED", "WORKS_FOR", "TRANSFERRED_TO", "PRESENT_AT"} else "") or "").strip().upper()
        if relationship_type in {"CALL", "TRANSACTION", "EVENT"} or (source_external and target_external and relationship_type):
            source = entity_by_external.get(source_external)
            target = entity_by_external.get(target_external)
            if source and target and source.id != target.id:
                relationship_type = {"CALL": "CALLS", "TRANSACTION": "TRANSFERRED_TO", "EVENT": "PRESENT_AT"}.get(relationship_type, relationship_type)
                db.add(Relationship(source_id=source.id, target_id=target.id, relationship_type=relationship_type, evidence_id=evidence.id, case_id=case_id, confidence=0.75, notes="Imported candidate relationship; analyst review required.", created_by_id=current_user.id))
                relationship_count += 1
    record_audit(db, action="CSV_IMPORTED", user_id=current_user.id, resource_type="EVIDENCE", resource_id=evidence.id, details={"filename": filename, "rows": len(rows), "entities_created": entity_count, "relationships_created": relationship_count})
    db.commit()
    return {"evidence_id": evidence.id, "rows": len(rows), "entities_created": entity_count, "relationships_created": relationship_count, "status": "REVIEW_REQUIRED"}
