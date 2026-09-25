from __future__ import annotations

import csv
import io
import mimetypes
import uuid
from datetime import UTC, datetime
from pathlib import Path

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile, status
from fastapi.responses import FileResponse
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..config import get_settings
from ..db import get_db
from ..dependencies import get_current_user, require_roles
from ..models import Case, Entity, Evidence, User, entity_evidence
from ..schemas import EvidenceOut
from ..services import record_audit

router = APIRouter(prefix="/evidence", tags=["evidence"])
settings = get_settings()

ALLOWED_EXTENSIONS = {".pdf", ".txt", ".csv", ".xlsx", ".xls", ".png", ".jpg", ".jpeg", ".webp"}
MAX_FILE_SIZE = 25 * 1024 * 1024


def evidence_to_out(evidence: Evidence) -> EvidenceOut:
    return EvidenceOut.model_validate(evidence)


def ensure_case(db: Session, case_id: str | None) -> None:
    if case_id and db.get(Case, case_id) is None:
        raise HTTPException(status_code=404, detail="Case not found")


def read_text_preview(content: bytes, extension: str) -> str:
    if extension in {".txt", ".csv"}:
        return content.decode("utf-8", errors="replace")[:500_000]
    if extension == ".csv":
        return content.decode("utf-8", errors="replace")[:500_000]
    return ""


@router.get("", response_model=list[EvidenceOut])
def list_evidence(
    _: User = Depends(get_current_user),
    db: Session = Depends(get_db),
    case_id: str | None = None,
    category: str | None = None,
    limit: int = 50,
) -> list[EvidenceOut]:
    statement = select(Evidence).order_by(Evidence.created_at.desc()).limit(min(limit, 200))
    if case_id:
        statement = statement.where(Evidence.case_id == case_id)
    if category:
        statement = statement.where(Evidence.category == category.upper())
    return [evidence_to_out(item) for item in db.scalars(statement).all()]


@router.get("/{evidence_id}", response_model=EvidenceOut)
def get_evidence(
    evidence_id: str,
    _: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> EvidenceOut:
    evidence = db.get(Evidence, evidence_id)
    if evidence is None:
        raise HTTPException(status_code=404, detail="Evidence not found")
    return evidence_to_out(evidence)


@router.get("/{evidence_id}/entities")
def linked_entities(
    evidence_id: str,
    _: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> list[dict[str, object]]:
    if db.get(Evidence, evidence_id) is None:
        raise HTTPException(status_code=404, detail="Evidence not found")
    links = db.scalars(select(entity_evidence).where(entity_evidence.evidence_id == evidence_id)).all()
    entities = db.scalars(select(Entity).where(Entity.id.in_([link.entity_id for link in links]))).all() if links else []
    return [{"id": entity.id, "name": entity.name, "entity_type": entity.entity_type, "relation": next((link.relation for link in links if link.entity_id == entity.id), "MENTIONED_IN")} for entity in entities]


@router.post("", response_model=EvidenceOut, status_code=status.HTTP_201_CREATED)
async def upload_evidence(
    current_user: User = Depends(require_roles("ADMIN")),
    db: Session = Depends(get_db),
    file: UploadFile = File(...),
    title: str = Form(...),
    category: str = Form("OTHER"),
    case_id: str | None = Form(default=None),
) -> EvidenceOut:
    original_filename = Path(file.filename or "upload.bin").name
    extension = Path(original_filename).suffix.lower()
    if extension not in ALLOWED_EXTENSIONS:
        raise HTTPException(status_code=415, detail=f"Unsupported file type: {extension or 'unknown'}")
    content = await file.read(MAX_FILE_SIZE + 1)
    if len(content) > MAX_FILE_SIZE:
        raise HTTPException(status_code=413, detail="File exceeds the 25 MB limit")
    if not content:
        raise HTTPException(status_code=422, detail="Uploaded file is empty")
    ensure_case(db, case_id)

    upload_root = settings.resolved_upload_dir.resolve()
    upload_root.mkdir(parents=True, exist_ok=True)
    stored_filename = f"{uuid.uuid4().hex}{extension}"
    storage_path = upload_root / stored_filename
    storage_path.write_bytes(content)
    content_type = file.content_type or mimetypes.guess_type(original_filename)[0] or "application/octet-stream"
    preview = read_text_preview(content, extension)
    evidence = Evidence(
        title=title.strip() or original_filename,
        original_filename=original_filename,
        stored_filename=stored_filename,
        content_type=content_type,
        size_bytes=len(content),
        category=category.strip().upper() or "OTHER",
        status="PROCESSED" if preview else "UPLOADED",
        storage_path=str(storage_path),
        extracted_text=preview,
        metadata_json={"extension": extension},
        case_id=case_id,
        uploaded_by_id=current_user.id,
        processed_at=datetime.now(UTC) if preview else None,
    )
    db.add(evidence)
    db.flush()
    record_audit(db, action="EVIDENCE_UPLOADED", user_id=current_user.id, resource_type="EVIDENCE", resource_id=evidence.id, details={"filename": original_filename, "category": evidence.category})
    db.commit()
    db.refresh(evidence)
    return evidence_to_out(evidence)


@router.get("/{evidence_id}/download")
def download_evidence(
    evidence_id: str,
    _: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> FileResponse:
    evidence = db.get(Evidence, evidence_id)
    if evidence is None:
        raise HTTPException(status_code=404, detail="Evidence not found")
    path = Path(evidence.storage_path).resolve()
    root = settings.resolved_upload_dir.resolve()
    try:
        path.relative_to(root)
    except ValueError as exc:
        raise HTTPException(status_code=403, detail="Evidence file is outside the managed storage root") from exc
    if not path.is_file():
        raise HTTPException(status_code=404, detail="Stored evidence file is missing")
    return FileResponse(path, media_type=evidence.content_type, filename=evidence.original_filename)


@router.post("/{evidence_id}/process", response_model=EvidenceOut)
def process_evidence(
    evidence_id: str,
    current_user: User = Depends(require_roles("ADMIN")),
    db: Session = Depends(get_db),
) -> EvidenceOut:
    evidence = db.get(Evidence, evidence_id)
    if evidence is None:
        raise HTTPException(status_code=404, detail="Evidence not found")
    path = Path(evidence.storage_path)
    if not path.is_file():
        evidence.status = "FAILED"
        record_audit(db, action="EVIDENCE_PROCESSING_FAILED", user_id=current_user.id, resource_type="EVIDENCE", resource_id=evidence.id, details={"reason": "missing file"})
        db.commit()
        raise HTTPException(status_code=404, detail="Stored evidence file is missing")
    extension = path.suffix.lower()
    content = path.read_bytes()
    preview = read_text_preview(content, extension)
    evidence.extracted_text = preview
    evidence.status = "PROCESSED" if preview else "UPLOADED"
    evidence.processed_at = datetime.now(UTC) if preview else None
    record_audit(db, action="EVIDENCE_PROCESSED", user_id=current_user.id, resource_type="EVIDENCE", resource_id=evidence.id, details={"has_text_preview": bool(preview)})
    db.commit()
    db.refresh(evidence)
    return evidence_to_out(evidence)
