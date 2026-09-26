from __future__ import annotations

import asyncio
import queue
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, UploadFile, WebSocket, WebSocketDisconnect, status
from fastapi.responses import Response
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from ..camera_graph import associate_observation_with_person, ensure_camera_graph_entities
from ..camera_manager import camera_manager
from ..camera_service import mask_source_uri, observation_to_dict
from ..camera_sources import HttpStreamSource, RTSPSource, VideoFileSource, WebcamSource
from ..config import get_settings
from ..db import get_db
from ..dependencies import get_current_user, get_user_from_token, require_roles
from ..models import Camera, CameraObservation, Case, Entity, Evidence, ObservationReview, PersonReferencePhoto, User
from ..schemas import (
    CameraCreate,
    CameraObservationOut,
    CameraOut,
    CameraStatusOut,
    CameraUpdate,
    ObservationReviewCreate,
    ObservationReviewOut,
    PersonReferencePhotoOut,
)
from ..services import record_audit

router = APIRouter(prefix="/cameras", tags=["camera monitoring"])
settings = get_settings()


def _validate_source(source_type: str, source_uri: str) -> None:
    try:
        if source_type == "WEBCAM":
            WebcamSource(source_uri)
        elif source_type == "VIDEO_FILE":
            VideoFileSource(source_uri)
        elif source_type == "HTTP_STREAM":
            HttpStreamSource(source_uri)
        elif source_type == "RTSP":
            RTSPSource(source_uri)
        else:
            raise ValueError(f"Unsupported source type: {source_type}")
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


def _validate_metadata(metadata: Any) -> None:
    """Reject malformed demo timelines at configuration time.

    A bad scripted-event definition must fail loudly when the camera is
    configured, not silently take a capture worker offline later.
    """
    if metadata is None:
        return
    if not isinstance(metadata, dict):
        raise HTTPException(status_code=422, detail="metadata must be an object")
    events = metadata.get("demo_events")
    if events is None:
        return
    if not isinstance(events, list):
        raise HTTPException(status_code=422, detail="metadata.demo_events must be a list of objects")
    for index, event in enumerate(events):
        if not isinstance(event, dict):
            raise HTTPException(status_code=422, detail=f"metadata.demo_events[{index}] must be an object")
        try:
            float(event.get("timestamp_seconds", event.get("timestamp", 0)))
        except (TypeError, ValueError) as exc:
            raise HTTPException(status_code=422, detail=f"metadata.demo_events[{index}].timestamp_seconds must be numeric") from exc
        bbox = event.get("bbox")
        if bbox is not None and not isinstance(bbox, dict):
            raise HTTPException(status_code=422, detail=f"metadata.demo_events[{index}].bbox must be an object")
        suggested = event.get("suggested_person_id")
        if suggested is not None and not isinstance(suggested, str):
            raise HTTPException(status_code=422, detail=f"metadata.demo_events[{index}].suggested_person_id must be a string")


def _camera_out(camera: Camera) -> CameraOut:
    return CameraOut(
        id=camera.id,
        camera_name=camera.camera_name,
        source_type=camera.source_type,
        source_uri_masked=mask_source_uri(camera.source_uri),
        location_id=camera.location_id,
        location_name=camera.location_name,
        latitude=camera.latitude,
        longitude=camera.longitude,
        timezone=camera.timezone,
        description=camera.description,
        enabled=camera.enabled,
        record_state=camera.record_state,
        status=camera.status,
        last_frame_at=camera.last_frame_at,
        last_detection_at=camera.last_detection_at,
        last_error=camera.last_error,
        detection_count=camera.detection_count,
        case_id=camera.case_id,
        created_by_id=camera.created_by_id,
        created_at=camera.created_at,
        updated_at=camera.updated_at,
        metadata=camera.metadata_json or {},
    )


def _observation_out(observation: CameraObservation, camera: Camera | None) -> CameraObservationOut:
    return CameraObservationOut.model_validate(observation_to_dict(observation, camera))


@router.get("", response_model=list[CameraOut])
def list_cameras(
    _: User = Depends(get_current_user),
    db: Session = Depends(get_db),
    location: str | None = Query(default=None, max_length=240),
    camera_status: str | None = Query(default=None, alias="status", max_length=24),
    include_archived: bool = False,
) -> list[CameraOut]:
    statement = select(Camera).order_by(Camera.created_at.desc())
    if not include_archived:
        statement = statement.where(Camera.record_state == "ACTIVE")
    if location:
        statement = statement.where(Camera.location_name.ilike(f"%{location}%"))
    if camera_status:
        statement = statement.where(Camera.status == camera_status.upper())
    return [_camera_out(camera) for camera in db.scalars(statement).all()]


@router.post("", response_model=CameraOut, status_code=status.HTTP_201_CREATED)
def create_camera(
    payload: CameraCreate,
    current_user: User = Depends(require_roles("ADMIN")),
    db: Session = Depends(get_db),
) -> CameraOut:
    _validate_source(payload.source_type, payload.source_uri)
    _validate_metadata(payload.metadata)
    if payload.case_id and db.get(Case, payload.case_id) is None:
        raise HTTPException(status_code=404, detail="Case not found")
    if payload.location_id:
        location = db.get(Entity, payload.location_id)
        if location is None or location.record_state != "ACTIVE":
            raise HTTPException(status_code=404, detail="Location entity not found")
    camera = Camera(
        camera_name=payload.camera_name.strip(),
        source_type=payload.source_type,
        source_uri=payload.source_uri.strip(),
        location_id=payload.location_id,
        location_name=payload.location_name.strip(),
        latitude=payload.latitude,
        longitude=payload.longitude,
        timezone=payload.timezone.strip() or "UTC",
        description=payload.description.strip(),
        enabled=payload.enabled,
        case_id=payload.case_id,
        created_by_id=current_user.id,
        metadata_json=payload.metadata,
    )
    db.add(camera)
    db.flush()
    ensure_camera_graph_entities(db, camera, actor_id=current_user.id)
    record_audit(db, action="CAMERA_CREATED", user_id=current_user.id, resource_type="CAMERA", resource_id=camera.id, details={"source_type": camera.source_type, "location_name": camera.location_name, "enabled": camera.enabled})
    db.commit()
    db.refresh(camera)
    return _camera_out(camera)


@router.get("/{camera_id}", response_model=CameraOut)
def get_camera(
    camera_id: str,
    _: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> CameraOut:
    camera = db.get(Camera, camera_id)
    if camera is None or camera.record_state == "ARCHIVED":
        raise HTTPException(status_code=404, detail="Camera not found")
    return _camera_out(camera)


@router.patch("/{camera_id}", response_model=CameraOut)
def update_camera(
    camera_id: str,
    payload: CameraUpdate,
    current_user: User = Depends(require_roles("ADMIN")),
    db: Session = Depends(get_db),
) -> CameraOut:
    camera = db.get(Camera, camera_id)
    if camera is None or camera.record_state == "ARCHIVED":
        raise HTTPException(status_code=404, detail="Camera not found")
    values = payload.model_dump(exclude_unset=True)
    next_type = values.get("source_type", camera.source_type)
    next_uri = values.get("source_uri", camera.source_uri)
    if "source_type" in values or "source_uri" in values:
        _validate_source(next_type, next_uri)
    if "metadata" in values:
        _validate_metadata(values["metadata"])
    if "case_id" in values and values["case_id"] and db.get(Case, values["case_id"]) is None:
        raise HTTPException(status_code=404, detail="Case not found")
    for field in ("camera_name", "source_type", "source_uri", "location_id", "location_name", "latitude", "longitude", "timezone", "description", "enabled", "case_id", "metadata"):
        if field in values:
            target_field = "metadata_json" if field == "metadata" else field
            setattr(camera, target_field, values[field])
    ensure_camera_graph_entities(db, camera, actor_id=current_user.id)
    record_audit(db, action="CAMERA_UPDATED", user_id=current_user.id, resource_type="CAMERA", resource_id=camera.id, details={"fields": list(values)})
    db.commit()
    db.refresh(camera)
    return _camera_out(camera)


@router.delete("/{camera_id}", status_code=status.HTTP_204_NO_CONTENT, response_class=Response, response_model=None)
def archive_camera(
    camera_id: str,
    current_user: User = Depends(require_roles("ADMIN")),
    db: Session = Depends(get_db),
) -> None:
    camera = db.get(Camera, camera_id)
    if camera is None or camera.record_state == "ARCHIVED":
        raise HTTPException(status_code=404, detail="Camera not found")
    try:
        camera_manager.stop_camera(camera_id, actor_id=current_user.id)
    except Exception:
        pass
    camera.enabled = False
    camera.record_state = "ARCHIVED"
    camera.status = "ARCHIVED"
    record_audit(db, action="CAMERA_ARCHIVED", user_id=current_user.id, resource_type="CAMERA", resource_id=camera.id)
    db.commit()


@router.post("/{camera_id}/start", response_model=CameraStatusOut)
def start_camera(
    camera_id: str,
    current_user: User = Depends(require_roles("ADMIN")),
    db: Session = Depends(get_db),
) -> CameraStatusOut:
    camera = db.get(Camera, camera_id)
    if camera is None or camera.record_state == "ARCHIVED":
        raise HTTPException(status_code=404, detail="Camera not found")
    try:
        camera_manager.start_camera(camera_id, actor_id=current_user.id)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    return CameraStatusOut(**camera_manager.status(camera_id))


@router.post("/{camera_id}/stop", response_model=CameraStatusOut)
def stop_camera(
    camera_id: str,
    current_user: User = Depends(require_roles("ADMIN")),
    db: Session = Depends(get_db),
) -> CameraStatusOut:
    if db.get(Camera, camera_id) is None:
        raise HTTPException(status_code=404, detail="Camera not found")
    camera_manager.stop_camera(camera_id, actor_id=current_user.id)
    return CameraStatusOut(**camera_manager.status(camera_id))


@router.get("/{camera_id}/status", response_model=CameraStatusOut)
def camera_status(
    camera_id: str,
    _: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> CameraStatusOut:
    if db.get(Camera, camera_id) is None:
        raise HTTPException(status_code=404, detail="Camera not found")
    return CameraStatusOut(**camera_manager.status(camera_id))


@router.get("/{camera_id}/latest-frame")
def latest_frame(
    camera_id: str,
    token: str | None = Query(default=None),
    db: Session = Depends(get_db),
) -> Response:
    if not token:
        raise HTTPException(status_code=401, detail="Token query parameter is required for frame access")
    get_user_from_token(token, db)
    frame = camera_manager.latest_frame(camera_id, annotated=True)
    if frame is None:
        raise HTTPException(status_code=404, detail="No frame is available for this camera")
    return Response(content=frame, media_type="image/jpeg", headers={"Cache-Control": "no-store"})


@router.get("/observations/all", response_model=list[CameraObservationOut])
def list_observations(
    _: User = Depends(get_current_user),
    db: Session = Depends(get_db),
    camera_id: str | None = None,
    review_status: str | None = Query(default=None, alias="status"),
    case_id: str | None = None,
    limit: int = Query(default=100, ge=1, le=500),
) -> list[CameraObservationOut]:
    statement = select(CameraObservation).options(selectinload(CameraObservation.reviews)).order_by(CameraObservation.created_at.desc()).limit(limit)
    if camera_id:
        statement = statement.where(CameraObservation.camera_id == camera_id)
    if review_status:
        statement = statement.where(CameraObservation.review_status == review_status.upper())
    if case_id:
        statement = statement.where(CameraObservation.case_id == case_id)
    observations = db.scalars(statement).all()
    cameras = {camera.id: camera for camera in db.scalars(select(Camera)).all()}
    return [_observation_out(observation, cameras.get(observation.camera_id)) for observation in observations]


@router.get("/observations/{observation_id}", response_model=CameraObservationOut)
def get_observation(
    observation_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> CameraObservationOut:
    observation = db.scalar(select(CameraObservation).options(selectinload(CameraObservation.reviews)).where(CameraObservation.id == observation_id))
    if observation is None:
        raise HTTPException(status_code=404, detail="Camera observation not found")
    camera = db.get(Camera, observation.camera_id)
    record_audit(db, action="CAMERA_EVIDENCE_VIEWED", user_id=current_user.id, resource_type="CAMERA_OBSERVATION", resource_id=observation.id)
    db.commit()
    return _observation_out(observation, camera)


@router.get("/observations/{observation_id}/annotated-frame")
def observation_annotated_frame(
    observation_id: str,
    token: str | None = Query(default=None),
    db: Session = Depends(get_db),
) -> Response:
    if not token:
        raise HTTPException(status_code=401, detail="Token query parameter is required for evidence access")
    get_user_from_token(token, db)
    observation = db.get(CameraObservation, observation_id)
    if observation is None or not observation.annotated_evidence_id:
        raise HTTPException(status_code=404, detail="Annotated frame is not available")
    evidence = db.get(Evidence, observation.annotated_evidence_id)
    if evidence is None or not Path(evidence.storage_path).is_file():
        raise HTTPException(status_code=404, detail="Annotated evidence file is missing")
    path = Path(evidence.storage_path).resolve()
    try:
        path.relative_to(settings.resolved_upload_dir.resolve())
    except ValueError as exc:
        raise HTTPException(status_code=403, detail="Evidence file is outside managed storage") from exc
    return Response(content=path.read_bytes(), media_type="image/jpeg", headers={"Cache-Control": "no-store"})


@router.post("/observations/{observation_id}/review", response_model=CameraObservationOut)
def review_observation(
    observation_id: str,
    payload: ObservationReviewCreate,
    current_user: User = Depends(require_roles("ADMIN", "ANALYST")),
    db: Session = Depends(get_db),
) -> CameraObservationOut:
    observation = db.scalar(select(CameraObservation).options(selectinload(CameraObservation.reviews)).where(CameraObservation.id == observation_id))
    if observation is None:
        raise HTTPException(status_code=404, detail="Camera observation not found")
    camera = db.get(Camera, observation.camera_id)
    if camera is None:
        raise HTTPException(status_code=404, detail="Camera not found")
    if observation.review_status != "PENDING_REVIEW":
        raise HTTPException(status_code=409, detail="Observation has already been reviewed")
    person: Entity | None = None
    if payload.decision == "ASSOCIATE":
        if not payload.associated_person_id:
            raise HTTPException(status_code=422, detail="associated_person_id is required for a manual association")
        person = db.get(Entity, payload.associated_person_id)
        if person is None or person.record_state != "ACTIVE" or person.entity_type != "PERSON":
            raise HTTPException(status_code=422, detail="associated_person_id must be an active Person entity")
    decision = payload.decision
    if decision == "VERIFY":
        observation.review_status = "VERIFIED_OBSERVATION"
    elif decision == "REJECT":
        observation.review_status = "REJECTED"
    else:
        observation.review_status = "ASSOCIATED_WITH_ENTITY"
        associate_observation_with_person(
            db,
            observation,
            camera,
            person,
            reviewer_id=current_user.id,
            evidence_id=observation.annotated_evidence_id or observation.evidence_id,
            notes=payload.notes,
        )
    review = ObservationReview(
        observation_id=observation.id,
        reviewer_id=current_user.id,
        decision=decision,
        associated_person_id=person.id if person else None,
        notes=payload.notes.strip(),
    )
    db.add(review)
    db.flush()
    record_audit(
        db,
        action="OBSERVATION_VERIFIED" if decision == "VERIFY" else "OBSERVATION_REJECTED" if decision == "REJECT" else "OBSERVATION_ASSOCIATED_WITH_PERSON",
        user_id=current_user.id,
        resource_type="CAMERA_OBSERVATION",
        resource_id=observation.id,
        details={"decision": decision, "associated_person_id": person.id if person else None, "human_reviewed": True, "biometric_identification": False},
    )
    db.commit()
    db.refresh(observation)
    camera_manager.publish("REVIEW_COMPLETED", camera.id, {"observation_id": observation.id, "review_status": observation.review_status})
    return _observation_out(observation, camera)


@router.post("/entities/{entity_id}/reference-photo", response_model=PersonReferencePhotoOut, status_code=status.HTTP_201_CREATED)
async def add_reference_photo(
    entity_id: str,
    file: UploadFile = File(...),
    label: str = Form("Reference photo"),
    notes: str = Form(""),
    current_user: User = Depends(require_roles("ADMIN")),
    db: Session = Depends(get_db),
) -> PersonReferencePhotoOut:
    entity = db.get(Entity, entity_id)
    if entity is None or entity.record_state != "ACTIVE" or entity.entity_type != "PERSON":
        raise HTTPException(status_code=404, detail="Active Person entity not found")
    extension = Path(file.filename or "photo.jpg").suffix.lower()
    if extension not in {".jpg", ".jpeg", ".png", ".webp"}:
        raise HTTPException(status_code=415, detail="Reference photos must be JPG, PNG, or WEBP")
    content = await file.read(10 * 1024 * 1024 + 1)
    if len(content) > 10 * 1024 * 1024:
        raise HTTPException(status_code=413, detail="Reference photo exceeds the 10 MB limit")
    root = settings.resolved_upload_dir.resolve() / "person-reference" / entity.id
    root.mkdir(parents=True, exist_ok=True)
    filename = f"{entity.id}-{abs(hash(content))}{extension}"
    path = root / filename
    path.write_bytes(content)
    evidence = Evidence(
        title=label.strip() or "Person reference photo",
        original_filename=Path(file.filename or filename).name,
        stored_filename=filename,
        content_type=file.content_type or "image/jpeg",
        size_bytes=len(content),
        category="PERSON_REFERENCE_PHOTO",
        status="PROCESSED",
        storage_path=str(path.resolve()),
        extracted_text="Reference photo for human review only; never used for biometric matching.",
        metadata_json={"entity_id": entity.id, "human_review_only": True, "biometric_matching": False},
        case_id=entity.case_id,
        uploaded_by_id=current_user.id,
    )
    db.add(evidence)
    db.flush()
    photo = PersonReferencePhoto(entity_id=entity.id, evidence_id=evidence.id, label=label.strip() or "Reference photo", notes=notes.strip(), created_by_id=current_user.id)
    db.add(photo)
    db.flush()
    record_audit(db, action="PERSON_REFERENCE_PHOTO_ADDED", user_id=current_user.id, resource_type="PERSON_REFERENCE_PHOTO", resource_id=photo.id, details={"entity_id": entity.id, "evidence_id": evidence.id, "biometric_matching": False})
    db.commit()
    db.refresh(photo)
    return PersonReferencePhotoOut.model_validate(photo)


@router.get("/entities/{entity_id}/reference-photos", response_model=list[PersonReferencePhotoOut])
def list_reference_photos(
    entity_id: str,
    _: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> list[PersonReferencePhotoOut]:
    return [PersonReferencePhotoOut.model_validate(item) for item in db.scalars(select(PersonReferencePhoto).where(PersonReferencePhoto.entity_id == entity_id).order_by(PersonReferencePhoto.created_at.desc())).all()]


@router.get("/entities/{entity_id}/reference-photos/{photo_id}/image")
def reference_photo_image(
    entity_id: str,
    photo_id: str,
    token: str | None = Query(default=None),
    db: Session = Depends(get_db),
) -> Response:
    if not token:
        raise HTTPException(status_code=401, detail="Token query parameter is required for photo access")
    get_user_from_token(token, db)
    photo = db.get(PersonReferencePhoto, photo_id)
    if photo is None or photo.entity_id != entity_id:
        raise HTTPException(status_code=404, detail="Reference photo not found")
    evidence = db.get(Evidence, photo.evidence_id)
    if evidence is None:
        raise HTTPException(status_code=404, detail="Reference photo evidence is missing")
    path = Path(evidence.storage_path).resolve()
    try:
        path.relative_to(settings.resolved_upload_dir.resolve())
    except ValueError as exc:
        raise HTTPException(status_code=403, detail="Reference photo is outside managed storage") from exc
    if not path.is_file():
        raise HTTPException(status_code=404, detail="Reference photo file is missing")
    return Response(content=path.read_bytes(), media_type=evidence.content_type, headers={"Cache-Control": "no-store"})


@router.websocket("/ws")
async def camera_events(websocket: WebSocket, token: str = Query(default="")) -> None:
    from ..db import SessionLocal

    db = SessionLocal()
    try:
        get_user_from_token(token, db)
    except HTTPException:
        db.close()
        await websocket.close(code=1008)
        return
    finally:
        db.close()
    await websocket.accept()
    subscriber = camera_manager.subscribe()
    await websocket.send_json({"event": "CAMERA_MONITOR_CONNECTED", "payload": {"demo_mode": settings.camera_demo_mode}})
    try:
        while True:
            try:
                event = subscriber.get_nowait()
            except queue.Empty:
                await asyncio.sleep(0.25)
                continue
            await websocket.send_json(event)
    except WebSocketDisconnect:
        pass
    finally:
        camera_manager.unsubscribe(subscriber)
