from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from ..db import get_db
from ..dependencies import get_current_user, require_roles
from ..models import AuditLog, Case, CaseNote, Entity, Evidence, Relationship, SavedGraphView, SavedSearch, User
from ..schemas import CaseCreate, CaseNoteCreate, CaseNoteOut, CaseOut, CaseUpdate, SavedGraphViewCreate, SavedGraphViewOut, SavedSearchCreate, SavedSearchOut
from ..services import record_audit

router = APIRouter(prefix="/cases", tags=["cases"])


def case_to_out(case: Case) -> CaseOut:
    return CaseOut.model_validate(case)


saved_router = APIRouter(prefix="/cases", tags=["saved investigations"])


@saved_router.get("/saved-searches", response_model=list[SavedSearchOut])
def list_saved_searches(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> list[SavedSearchOut]:
    return [SavedSearchOut.model_validate(item) for item in db.scalars(select(SavedSearch).where(SavedSearch.owner_id == current_user.id).order_by(SavedSearch.created_at.desc())).all()]


@saved_router.post("/saved-searches", response_model=SavedSearchOut, status_code=status.HTTP_201_CREATED)
def create_saved_search(
    payload: SavedSearchCreate,
    current_user: User = Depends(require_roles("ADMIN", "ANALYST")),
    db: Session = Depends(get_db),
) -> SavedSearchOut:
    if payload.case_id and db.get(Case, payload.case_id) is None:
        raise HTTPException(status_code=404, detail="Case not found")
    item = SavedSearch(name=payload.name.strip(), owner_id=current_user.id, case_id=payload.case_id, query=payload.query.strip(), filters_json=payload.filters)
    db.add(item)
    db.flush()
    record_audit(db, action="SAVED_SEARCH_CREATED", user_id=current_user.id, resource_type="SAVED_SEARCH", resource_id=item.id, details={"case_id": payload.case_id})
    db.commit()
    db.refresh(item)
    return SavedSearchOut.model_validate(item)


@saved_router.get("/saved-views", response_model=list[SavedGraphViewOut])
def list_saved_views(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> list[SavedGraphViewOut]:
    return [SavedGraphViewOut.model_validate(item) for item in db.scalars(select(SavedGraphView).where(SavedGraphView.owner_id == current_user.id).order_by(SavedGraphView.created_at.desc())).all()]


@saved_router.post("/saved-views", response_model=SavedGraphViewOut, status_code=status.HTTP_201_CREATED)
def create_saved_view(
    payload: SavedGraphViewCreate,
    current_user: User = Depends(require_roles("ADMIN", "ANALYST")),
    db: Session = Depends(get_db),
) -> SavedGraphViewOut:
    if payload.case_id and db.get(Case, payload.case_id) is None:
        raise HTTPException(status_code=404, detail="Case not found")
    if payload.center_id and db.get(Entity, payload.center_id) is None:
        raise HTTPException(status_code=404, detail="Center entity not found")
    item = SavedGraphView(name=payload.name.strip(), owner_id=current_user.id, case_id=payload.case_id, center_id=payload.center_id, depth=payload.depth, filters_json=payload.filters)
    db.add(item)
    db.flush()
    record_audit(db, action="SAVED_GRAPH_VIEW_CREATED", user_id=current_user.id, resource_type="SAVED_GRAPH_VIEW", resource_id=item.id, details={"case_id": payload.case_id, "center_id": payload.center_id})
    db.commit()
    db.refresh(item)
    return SavedGraphViewOut.model_validate(item)


@router.get("", response_model=list[CaseOut])
def list_cases(
    _: User = Depends(get_current_user),
    db: Session = Depends(get_db),
    status_filter: str | None = None,
) -> list[CaseOut]:
    statement = select(Case).order_by(Case.updated_at.desc())
    if status_filter:
        statement = statement.where(Case.status == status_filter.upper())
    return [case_to_out(case) for case in db.scalars(statement).all()]


@router.get("/{case_id}", response_model=CaseOut)
def get_case(
    case_id: str,
    _: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> CaseOut:
    case = db.get(Case, case_id)
    if case is None:
        raise HTTPException(status_code=404, detail="Case not found")
    return case_to_out(case)


@router.get("/{case_id}/notes", response_model=list[CaseNoteOut])
def list_case_notes(
    case_id: str,
    _: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> list[CaseNoteOut]:
    if db.get(Case, case_id) is None:
        raise HTTPException(status_code=404, detail="Case not found")
    return [CaseNoteOut.model_validate(note) for note in db.scalars(select(CaseNote).where(CaseNote.case_id == case_id).order_by(CaseNote.created_at.desc())).all()]


@router.post("/{case_id}/notes", response_model=CaseNoteOut, status_code=status.HTTP_201_CREATED)
def add_case_note(
    case_id: str,
    payload: CaseNoteCreate,
    current_user: User = Depends(require_roles("ADMIN", "ANALYST")),
    db: Session = Depends(get_db),
) -> CaseNoteOut:
    if db.get(Case, case_id) is None:
        raise HTTPException(status_code=404, detail="Case not found")
    note = CaseNote(case_id=case_id, user_id=current_user.id, body=payload.body.strip())
    db.add(note)
    db.flush()
    record_audit(db, action="CASE_NOTE_ADDED", user_id=current_user.id, resource_type="CASE", resource_id=case_id, details={"note_id": note.id})
    db.commit()
    db.refresh(note)
    return CaseNoteOut.model_validate(note)


@router.get("/{case_id}/history")
def case_history(
    case_id: str,
    _: User = Depends(require_roles("ADMIN", "ANALYST", "AUDITOR")),
    db: Session = Depends(get_db),
) -> list[dict[str, object]]:
    if db.get(Case, case_id) is None:
        raise HTTPException(status_code=404, detail="Case not found")
    events = db.scalars(select(AuditLog).where(AuditLog.resource_id == case_id).order_by(AuditLog.created_at.desc()).limit(200)).all()
    return [{"id": event.id, "action": event.action, "user_id": event.user_id, "details": event.details_json, "created_at": event.created_at.isoformat()} for event in events]


@router.post("", response_model=CaseOut, status_code=status.HTTP_201_CREATED)
def create_case(
    payload: CaseCreate,
    current_user: User = Depends(require_roles("ADMIN", "ANALYST")),
    db: Session = Depends(get_db),
) -> CaseOut:
    if db.scalar(select(Case).where(Case.case_number == payload.case_number.strip().upper())):
        raise HTTPException(status_code=409, detail="Case number already exists")
    case = Case(
        case_number=payload.case_number.strip().upper(),
        title=payload.title.strip(),
        description=payload.description.strip(),
        status=payload.status.upper(),
        priority=payload.priority.upper(),
        created_by_id=current_user.id,
    )
    db.add(case)
    db.flush()
    record_audit(db, action="CASE_CREATED", user_id=current_user.id, resource_type="CASE", resource_id=case.id, details={"case_number": case.case_number})
    db.commit()
    db.refresh(case)
    return case_to_out(case)


@router.patch("/{case_id}", response_model=CaseOut)
def update_case(
    case_id: str,
    payload: CaseUpdate,
    current_user: User = Depends(require_roles("ADMIN", "ANALYST")),
    db: Session = Depends(get_db),
) -> CaseOut:
    case = db.get(Case, case_id)
    if case is None:
        raise HTTPException(status_code=404, detail="Case not found")
    values = payload.model_dump(exclude_unset=True)
    for field in ("title", "description", "status", "priority"):
        if field in values and values[field] is not None:
            setattr(case, field, values[field].strip() if isinstance(values[field], str) else values[field])
    record_audit(db, action="CASE_UPDATED", user_id=current_user.id, resource_type="CASE", resource_id=case.id, details={"fields": list(values)})
    db.commit()
    db.refresh(case)
    return case_to_out(case)


@router.post("/{case_id}/entities/{entity_id}", status_code=status.HTTP_204_NO_CONTENT, response_class=Response, response_model=None)
def attach_entity(
    case_id: str,
    entity_id: str,
    current_user: User = Depends(require_roles("ADMIN", "ANALYST")),
    db: Session = Depends(get_db),
) -> None:
    case = db.get(Case, case_id)
    entity = db.get(Entity, entity_id)
    if case is None or entity is None:
        raise HTTPException(status_code=404, detail="Case or entity not found")
    entity.case_id = case_id
    record_audit(db, action="CASE_ENTITY_ATTACHED", user_id=current_user.id, resource_type="CASE", resource_id=case_id, details={"entity_id": entity_id})
    db.commit()


@router.post("/{case_id}/evidence/{evidence_id}", status_code=status.HTTP_204_NO_CONTENT, response_class=Response, response_model=None)
def attach_evidence(
    case_id: str,
    evidence_id: str,
    current_user: User = Depends(require_roles("ADMIN", "ANALYST")),
    db: Session = Depends(get_db),
) -> None:
    case = db.get(Case, case_id)
    evidence = db.get(Evidence, evidence_id)
    if case is None or evidence is None:
        raise HTTPException(status_code=404, detail="Case or evidence not found")
    evidence.case_id = case_id
    record_audit(db, action="CASE_EVIDENCE_ATTACHED", user_id=current_user.id, resource_type="CASE", resource_id=case_id, details={"evidence_id": evidence_id})
    db.commit()
