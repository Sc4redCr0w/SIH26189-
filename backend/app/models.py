from __future__ import annotations

from datetime import UTC, datetime
from typing import Any
from uuid import uuid4

from sqlalchemy import JSON, Boolean, DateTime, Float, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .db import Base


def utc_now() -> datetime:
    return datetime.now(UTC)


def new_id(prefix: str) -> str:
    return f"{prefix}-{uuid4().hex[:12]}"


class User(Base):
    __tablename__ = "users"

    id: Mapped[str] = mapped_column(String(40), primary_key=True, default=lambda: new_id("USR"))
    username: Mapped[str] = mapped_column(String(80), unique=True, index=True)
    display_name: Mapped[str] = mapped_column(String(120))
    password_hash: Mapped[str] = mapped_column(String(512))
    role: Mapped[str] = mapped_column(String(24), index=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
    last_login_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    entities: Mapped[list[Entity]] = relationship(back_populates="created_by")
    relationships: Mapped[list[Relationship]] = relationship(back_populates="created_by")
    evidence: Mapped[list[Evidence]] = relationship(back_populates="uploaded_by")
    audit_events: Mapped[list[AuditLog]] = relationship(back_populates="user")


class Case(Base):
    __tablename__ = "cases"

    id: Mapped[str] = mapped_column(String(40), primary_key=True, default=lambda: new_id("CASE"))
    case_number: Mapped[str] = mapped_column(String(80), unique=True, index=True)
    title: Mapped[str] = mapped_column(String(240))
    description: Mapped[str] = mapped_column(Text, default="")
    status: Mapped[str] = mapped_column(String(32), default="ACTIVE", index=True)
    priority: Mapped[str] = mapped_column(String(24), default="MEDIUM")
    created_by_id: Mapped[str | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, onupdate=utc_now)

    created_by: Mapped[User | None] = relationship()
    entities: Mapped[list[Entity]] = relationship(back_populates="case")
    evidence: Mapped[list[Evidence]] = relationship(back_populates="case")
    relationships: Mapped[list[Relationship]] = relationship(back_populates="case")
    reports: Mapped[list[Report]] = relationship(back_populates="case")


class CaseNote(Base):
    __tablename__ = "case_notes"

    id: Mapped[str] = mapped_column(String(40), primary_key=True, default=lambda: new_id("NOTE"))
    case_id: Mapped[str] = mapped_column(ForeignKey("cases.id"), index=True)
    user_id: Mapped[str | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    body: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, index=True)

    case: Mapped[Case] = relationship()
    user: Mapped[User | None] = relationship()


class SavedSearch(Base):
    __tablename__ = "saved_searches"

    id: Mapped[str] = mapped_column(String(40), primary_key=True, default=lambda: new_id("SEARCH"))
    name: Mapped[str] = mapped_column(String(160))
    owner_id: Mapped[str] = mapped_column(ForeignKey("users.id"), index=True)
    case_id: Mapped[str | None] = mapped_column(ForeignKey("cases.id"), nullable=True, index=True)
    query: Mapped[str] = mapped_column(String(1000))
    filters_json: Mapped[dict[str, Any]] = mapped_column("filters", JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)

    owner: Mapped[User] = relationship()
    case: Mapped[Case | None] = relationship()


class SavedGraphView(Base):
    __tablename__ = "saved_graph_views"

    id: Mapped[str] = mapped_column(String(40), primary_key=True, default=lambda: new_id("VIEW"))
    name: Mapped[str] = mapped_column(String(160))
    owner_id: Mapped[str] = mapped_column(ForeignKey("users.id"), index=True)
    case_id: Mapped[str | None] = mapped_column(ForeignKey("cases.id"), nullable=True, index=True)
    center_id: Mapped[str | None] = mapped_column(String(40), nullable=True)
    depth: Mapped[int] = mapped_column(Integer, default=2)
    filters_json: Mapped[dict[str, Any]] = mapped_column("filters", JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)

    owner: Mapped[User] = relationship()
    case: Mapped[Case | None] = relationship()


class Entity(Base):
    __tablename__ = "entities"

    id: Mapped[str] = mapped_column(String(40), primary_key=True, default=lambda: new_id("ENT"))
    name: Mapped[str] = mapped_column(String(240), index=True)
    normalized_name: Mapped[str] = mapped_column(String(240), index=True)
    entity_type: Mapped[str] = mapped_column(String(32), index=True)
    aliases: Mapped[list[str]] = mapped_column(JSON, default=list)
    status: Mapped[str] = mapped_column(String(40), default="UNKNOWN", index=True)
    record_state: Mapped[str] = mapped_column(String(24), default="ACTIVE", index=True)
    notes: Mapped[str] = mapped_column(Text, default="")
    metadata_json: Mapped[dict[str, Any]] = mapped_column("metadata", JSON, default=dict)
    case_id: Mapped[str | None] = mapped_column(ForeignKey("cases.id"), nullable=True, index=True)
    created_by_id: Mapped[str | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, onupdate=utc_now)

    created_by: Mapped[User | None] = relationship(back_populates="entities")
    case: Mapped[Case | None] = relationship(back_populates="entities")
    outgoing_relationships: Mapped[list[Relationship]] = relationship(
        back_populates="source_entity", foreign_keys="Relationship.source_id"
    )
    incoming_relationships: Mapped[list[Relationship]] = relationship(
        back_populates="target_entity", foreign_keys="Relationship.target_id"
    )
    evidence_links: Mapped[list[Evidence]] = relationship(secondary="entity_evidence", viewonly=True)


class Evidence(Base):
    __tablename__ = "evidence"

    id: Mapped[str] = mapped_column(String(40), primary_key=True, default=lambda: new_id("EVD"))
    title: Mapped[str] = mapped_column(String(240))
    original_filename: Mapped[str] = mapped_column(String(255))
    stored_filename: Mapped[str] = mapped_column(String(255))
    content_type: Mapped[str] = mapped_column(String(160), default="application/octet-stream")
    size_bytes: Mapped[int] = mapped_column(Integer, default=0)
    category: Mapped[str] = mapped_column(String(64), default="OTHER", index=True)
    status: Mapped[str] = mapped_column(String(24), default="UPLOADED", index=True)
    storage_path: Mapped[str] = mapped_column(String(500))
    extracted_text: Mapped[str] = mapped_column(Text, default="")
    metadata_json: Mapped[dict[str, Any]] = mapped_column("metadata", JSON, default=dict)
    case_id: Mapped[str | None] = mapped_column(ForeignKey("cases.id"), nullable=True, index=True)
    uploaded_by_id: Mapped[str | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
    processed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    uploaded_by: Mapped[User | None] = relationship(back_populates="evidence")
    case: Mapped[Case | None] = relationship(back_populates="evidence")
    entities: Mapped[list[Entity]] = relationship(secondary="entity_evidence", viewonly=True)
    relationships: Mapped[list[Relationship]] = relationship(back_populates="evidence")


class entity_evidence(Base):  # noqa: N801 - association table follows SQLAlchemy convention
    __tablename__ = "entity_evidence"

    entity_id: Mapped[str] = mapped_column(ForeignKey("entities.id"), primary_key=True)
    evidence_id: Mapped[str] = mapped_column(ForeignKey("evidence.id"), primary_key=True)
    relation: Mapped[str] = mapped_column(String(32), default="MENTIONED_IN")


class Camera(Base):
    __tablename__ = "cameras"

    id: Mapped[str] = mapped_column(String(40), primary_key=True, default=lambda: new_id("CAM"))
    camera_name: Mapped[str] = mapped_column(String(160), index=True)
    source_type: Mapped[str] = mapped_column(String(32), index=True)
    source_uri: Mapped[str] = mapped_column(String(1000))
    location_id: Mapped[str | None] = mapped_column(ForeignKey("entities.id"), nullable=True, index=True)
    location_name: Mapped[str] = mapped_column(String(240), default="")
    latitude: Mapped[float | None] = mapped_column(Float, nullable=True)
    longitude: Mapped[float | None] = mapped_column(Float, nullable=True)
    timezone: Mapped[str] = mapped_column(String(64), default="UTC")
    description: Mapped[str] = mapped_column(Text, default="")
    enabled: Mapped[bool] = mapped_column(Boolean, default=True, index=True)
    record_state: Mapped[str] = mapped_column(String(24), default="ACTIVE", index=True)
    status: Mapped[str] = mapped_column(String(24), default="STOPPED", index=True)
    last_frame_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    last_detection_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    last_error: Mapped[str] = mapped_column(Text, default="")
    detection_count: Mapped[int] = mapped_column(Integer, default=0)
    case_id: Mapped[str | None] = mapped_column(ForeignKey("cases.id"), nullable=True, index=True)
    created_by_id: Mapped[str | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, onupdate=utc_now)
    metadata_json: Mapped[dict[str, Any]] = mapped_column("metadata", JSON, default=dict)

    created_by: Mapped[User | None] = relationship()
    observations: Mapped[list[CameraObservation]] = relationship(back_populates="camera", cascade="all, delete-orphan")


class CameraObservation(Base):
    __tablename__ = "camera_observations"

    id: Mapped[str] = mapped_column(String(40), primary_key=True, default=lambda: new_id("OBS"))
    camera_id: Mapped[str] = mapped_column(ForeignKey("cameras.id"), index=True)
    timestamp: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, index=True)
    frame_number: Mapped[int] = mapped_column(Integer, default=0)
    bbox_x: Mapped[int] = mapped_column(Integer, default=0)
    bbox_y: Mapped[int] = mapped_column(Integer, default=0)
    bbox_width: Mapped[int] = mapped_column(Integer, default=0)
    bbox_height: Mapped[int] = mapped_column(Integer, default=0)
    detection_confidence: Mapped[float | None] = mapped_column(Float, nullable=True)
    confidence_method: Mapped[str] = mapped_column(String(80), default="HAAR_CASCADE_BINARY")
    evidence_id: Mapped[str | None] = mapped_column(ForeignKey("evidence.id"), nullable=True, index=True)
    annotated_evidence_id: Mapped[str | None] = mapped_column(ForeignKey("evidence.id"), nullable=True)
    clip_evidence_id: Mapped[str | None] = mapped_column(ForeignKey("evidence.id"), nullable=True)
    location_id: Mapped[str | None] = mapped_column(ForeignKey("entities.id"), nullable=True, index=True)
    location_name: Mapped[str] = mapped_column(String(240), default="")
    case_id: Mapped[str | None] = mapped_column(ForeignKey("cases.id"), nullable=True, index=True)
    review_status: Mapped[str] = mapped_column(String(32), default="PENDING_REVIEW", index=True)
    is_simulated: Mapped[bool] = mapped_column(Boolean, default=False, index=True)
    simulation_label: Mapped[str] = mapped_column(String(240), default="")
    suggested_person_id: Mapped[str | None] = mapped_column(ForeignKey("entities.id"), nullable=True)
    created_by_id: Mapped[str | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, index=True)
    metadata_json: Mapped[dict[str, Any]] = mapped_column("metadata", JSON, default=dict)

    camera: Mapped[Camera] = relationship(back_populates="observations")
    reviews: Mapped[list[ObservationReview]] = relationship(back_populates="observation", cascade="all, delete-orphan")
    evidence_links: Mapped[list[CameraEvidence]] = relationship(back_populates="observation", cascade="all, delete-orphan")


class CameraEvidence(Base):
    __tablename__ = "camera_evidence"

    id: Mapped[str] = mapped_column(String(40), primary_key=True, default=lambda: new_id("CEV"))
    observation_id: Mapped[str] = mapped_column(ForeignKey("camera_observations.id"), index=True)
    evidence_id: Mapped[str] = mapped_column(ForeignKey("evidence.id"), index=True)
    kind: Mapped[str] = mapped_column(String(32), default="RAW_FRAME")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)

    observation: Mapped[CameraObservation] = relationship(back_populates="evidence_links")
    evidence: Mapped[Evidence] = relationship()


class ObservationReview(Base):
    __tablename__ = "observation_reviews"

    id: Mapped[str] = mapped_column(String(40), primary_key=True, default=lambda: new_id("REV"))
    observation_id: Mapped[str] = mapped_column(ForeignKey("camera_observations.id"), index=True)
    reviewer_id: Mapped[str] = mapped_column(ForeignKey("users.id"), nullable=True, index=True)
    decision: Mapped[str] = mapped_column(String(32), index=True)
    associated_person_id: Mapped[str | None] = mapped_column(ForeignKey("entities.id"), nullable=True, index=True)
    notes: Mapped[str] = mapped_column(Text, default="")
    reviewed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, index=True)

    observation: Mapped[CameraObservation] = relationship(back_populates="reviews")
    reviewer: Mapped[User | None] = relationship()
    associated_person: Mapped[Entity | None] = relationship(foreign_keys=[associated_person_id])


class PersonReferencePhoto(Base):
    __tablename__ = "person_reference_photos"

    id: Mapped[str] = mapped_column(String(40), primary_key=True, default=lambda: new_id("PREF"))
    entity_id: Mapped[str] = mapped_column(ForeignKey("entities.id"), index=True)
    evidence_id: Mapped[str] = mapped_column(ForeignKey("evidence.id"), index=True)
    label: Mapped[str] = mapped_column(String(160), default="Reference photo")
    notes: Mapped[str] = mapped_column(Text, default="")
    created_by_id: Mapped[str | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)

    entity: Mapped[Entity] = relationship()
    evidence: Mapped[Evidence] = relationship()
    created_by: Mapped[User | None] = relationship()


class Relationship(Base):
    __tablename__ = "relationships"

    id: Mapped[str] = mapped_column(String(40), primary_key=True, default=lambda: new_id("REL"))
    source_id: Mapped[str] = mapped_column(ForeignKey("entities.id"), index=True)
    target_id: Mapped[str] = mapped_column(ForeignKey("entities.id"), index=True)
    relationship_type: Mapped[str] = mapped_column(String(48), index=True)
    timestamp: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    start_time: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    end_time: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    evidence_id: Mapped[str | None] = mapped_column(ForeignKey("evidence.id"), nullable=True, index=True)
    case_id: Mapped[str | None] = mapped_column(ForeignKey("cases.id"), nullable=True, index=True)
    confidence: Mapped[float] = mapped_column(Float, default=1.0)
    notes: Mapped[str] = mapped_column(Text, default="")
    record_state: Mapped[str] = mapped_column(String(24), default="TRUSTED", index=True)
    created_by_id: Mapped[str | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, onupdate=utc_now)

    source_entity: Mapped[Entity] = relationship(back_populates="outgoing_relationships", foreign_keys=[source_id])
    target_entity: Mapped[Entity] = relationship(back_populates="incoming_relationships", foreign_keys=[target_id])
    evidence: Mapped[Evidence | None] = relationship(back_populates="relationships")
    case: Mapped[Case | None] = relationship(back_populates="relationships")
    created_by: Mapped[User | None] = relationship(back_populates="relationships")


class ExtractionCandidate(Base):
    __tablename__ = "extraction_candidates"

    id: Mapped[str] = mapped_column(String(40), primary_key=True, default=lambda: new_id("CAND"))
    evidence_id: Mapped[str] = mapped_column(ForeignKey("evidence.id"), index=True)
    candidate_type: Mapped[str] = mapped_column(String(32), index=True)
    value: Mapped[str] = mapped_column(String(500))
    normalized_value: Mapped[str] = mapped_column(String(500), index=True)
    confidence: Mapped[float] = mapped_column(Float, default=0.5)
    source_span: Mapped[str] = mapped_column(String(500), default="")
    status: Mapped[str] = mapped_column(String(24), default="PENDING", index=True)
    entity_id: Mapped[str | None] = mapped_column(ForeignKey("entities.id"), nullable=True)
    reviewed_by_id: Mapped[str | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
    reviewed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    evidence: Mapped[Evidence] = relationship()
    entity: Mapped[Entity | None] = relationship()


class AnalysisRun(Base):
    __tablename__ = "analysis_runs"

    id: Mapped[str] = mapped_column(String(40), primary_key=True, default=lambda: new_id("RUN"))
    case_id: Mapped[str | None] = mapped_column(ForeignKey("cases.id"), nullable=True, index=True)
    algorithm: Mapped[str] = mapped_column(String(64), index=True)
    parameters_json: Mapped[dict[str, Any]] = mapped_column("parameters", JSON, default=dict)
    result_json: Mapped[dict[str, Any]] = mapped_column("result", JSON, default=dict)
    status: Mapped[str] = mapped_column(String(24), default="COMPLETED", index=True)
    created_by_id: Mapped[str | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)

    created_by: Mapped[User | None] = relationship()
    case: Mapped[Case | None] = relationship()


class Report(Base):
    __tablename__ = "reports"

    id: Mapped[str] = mapped_column(String(40), primary_key=True, default=lambda: new_id("RPT"))
    case_id: Mapped[str | None] = mapped_column(ForeignKey("cases.id"), nullable=True, index=True)
    title: Mapped[str] = mapped_column(String(240))
    summary: Mapped[str] = mapped_column(Text, default="")
    content_json: Mapped[dict[str, Any]] = mapped_column("content", JSON, default=dict)
    version: Mapped[int] = mapped_column(Integer, default=1)
    created_by_id: Mapped[str | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)

    created_by: Mapped[User | None] = relationship()
    case: Mapped[Case | None] = relationship(back_populates="reports")


class AuditLog(Base):
    __tablename__ = "audit_logs"

    id: Mapped[str] = mapped_column(String(40), primary_key=True, default=lambda: new_id("AUD"))
    user_id: Mapped[str | None] = mapped_column(ForeignKey("users.id"), nullable=True, index=True)
    action: Mapped[str] = mapped_column(String(64), index=True)
    resource_type: Mapped[str | None] = mapped_column(String(64), nullable=True)
    resource_id: Mapped[str | None] = mapped_column(String(64), nullable=True, index=True)
    details_json: Mapped[dict[str, Any]] = mapped_column("details", JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, index=True)

    user: Mapped[User | None] = relationship(back_populates="audit_events")


class RevokedToken(Base):
    __tablename__ = "revoked_tokens"

    jti: Mapped[str] = mapped_column(String(64), primary_key=True)
    user_id: Mapped[str | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
