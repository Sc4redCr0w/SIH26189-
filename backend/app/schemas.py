from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator


class ORMModel(BaseModel):
    model_config = ConfigDict(from_attributes=True)


class LoginRequest(BaseModel):
    username: str = Field(min_length=2, max_length=80)
    password: str = Field(min_length=8, max_length=256)


class UserOut(ORMModel):
    id: str
    username: str
    display_name: str
    role: str
    is_active: bool
    created_at: datetime
    last_login_at: datetime | None = None


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    expires_in: int
    user: UserOut


class UserCreate(BaseModel):
    username: str = Field(min_length=2, max_length=80)
    display_name: str = Field(min_length=2, max_length=120)
    password: str = Field(min_length=12, max_length=256)
    role: str = Field(pattern="^(ADMIN|ANALYST|AUDITOR)$")


class UserUpdate(BaseModel):
    display_name: str | None = Field(default=None, min_length=2, max_length=120)
    role: str | None = Field(default=None, pattern="^(ADMIN|ANALYST|AUDITOR)$")
    is_active: bool | None = None
    password: str | None = Field(default=None, min_length=12, max_length=256)


class EntityCreate(BaseModel):
    name: str = Field(min_length=2, max_length=240)
    entity_type: str = Field(min_length=2, max_length=32)
    aliases: list[str] = Field(default_factory=list)
    status: str = Field(default="UNKNOWN", max_length=40)
    notes: str = Field(default="", max_length=10000)
    metadata: dict[str, Any] = Field(default_factory=dict)
    case_id: str | None = None

    @field_validator("entity_type")
    @classmethod
    def normalize_type(cls, value: str) -> str:
        return value.strip().upper()

    @field_validator("aliases")
    @classmethod
    def clean_aliases(cls, value: list[str]) -> list[str]:
        return list(dict.fromkeys(item.strip() for item in value if item.strip()))


class EntityUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=2, max_length=240)
    entity_type: str | None = Field(default=None, min_length=2, max_length=32)
    aliases: list[str] | None = None
    status: str | None = Field(default=None, max_length=40)
    notes: str | None = Field(default=None, max_length=10000)
    metadata: dict[str, Any] | None = None
    case_id: str | None = None


class EntityMerge(BaseModel):
    target_entity_id: str = Field(min_length=3, max_length=40)
    reason: str = Field(min_length=8, max_length=2000)
    confirm: bool = False


class EntityOut(ORMModel):
    id: str
    name: str
    normalized_name: str
    entity_type: str
    aliases: list[str]
    status: str
    record_state: str
    notes: str
    metadata: dict[str, Any] = Field(default_factory=dict, validation_alias="metadata_json")
    case_id: str | None = None
    created_by_id: str | None = None
    created_at: datetime
    updated_at: datetime


class DuplicateMatch(BaseModel):
    entity_id: str
    name: str
    entity_type: str
    score: float
    signals: list[str]
    recommendation: str


class RelationshipCreate(BaseModel):
    source_id: str
    target_id: str
    relationship_type: str = Field(min_length=2, max_length=48)
    timestamp: datetime | None = None
    start_time: datetime | None = None
    end_time: datetime | None = None
    evidence_id: str | None = None
    case_id: str | None = None
    confidence: float = Field(default=1.0, ge=0.0, le=1.0)
    notes: str = Field(default="", max_length=10000)

    @field_validator("relationship_type")
    @classmethod
    def normalize_relationship(cls, value: str) -> str:
        return value.strip().upper().replace(" ", "_")


class RelationshipUpdate(BaseModel):
    relationship_type: str | None = Field(default=None, min_length=2, max_length=48)
    timestamp: datetime | None = None
    start_time: datetime | None = None
    end_time: datetime | None = None
    evidence_id: str | None = None
    case_id: str | None = None
    confidence: float | None = Field(default=None, ge=0.0, le=1.0)
    notes: str | None = Field(default=None, max_length=10000)


class RelationshipOut(ORMModel):
    id: str
    source_id: str
    target_id: str
    relationship_type: str
    timestamp: datetime | None = None
    start_time: datetime | None = None
    end_time: datetime | None = None
    evidence_id: str | None = None
    case_id: str | None = None
    confidence: float
    notes: str
    record_state: str
    created_by_id: str | None = None
    created_at: datetime
    updated_at: datetime


class CaseCreate(BaseModel):
    case_number: str = Field(min_length=3, max_length=80)
    title: str = Field(min_length=3, max_length=240)
    description: str = Field(default="", max_length=20000)
    status: str = Field(default="ACTIVE", max_length=32)
    priority: str = Field(default="MEDIUM", max_length=24)


class CaseUpdate(BaseModel):
    title: str | None = Field(default=None, min_length=3, max_length=240)
    description: str | None = Field(default=None, max_length=20000)
    status: str | None = Field(default=None, max_length=32)
    priority: str | None = Field(default=None, max_length=24)


class CaseOut(ORMModel):
    id: str
    case_number: str
    title: str
    description: str
    status: str
    priority: str
    created_by_id: str | None = None
    created_at: datetime
    updated_at: datetime


class CaseNoteCreate(BaseModel):
    body: str = Field(min_length=2, max_length=10000)


class CaseNoteOut(ORMModel):
    id: str
    case_id: str
    user_id: str | None = None
    body: str
    created_at: datetime


class SavedSearchCreate(BaseModel):
    name: str = Field(min_length=2, max_length=160)
    query: str = Field(min_length=1, max_length=1000)
    case_id: str | None = None
    filters: dict[str, Any] = Field(default_factory=dict)


class SavedSearchOut(ORMModel):
    id: str
    name: str
    owner_id: str
    case_id: str | None = None
    query: str
    filters: dict[str, Any] = Field(default_factory=dict, validation_alias="filters_json")
    created_at: datetime


class SavedGraphViewCreate(BaseModel):
    name: str = Field(min_length=2, max_length=160)
    case_id: str | None = None
    center_id: str | None = None
    depth: int = Field(default=2, ge=1, le=5)
    filters: dict[str, Any] = Field(default_factory=dict)


class SavedGraphViewOut(ORMModel):
    id: str
    name: str
    owner_id: str
    case_id: str | None = None
    center_id: str | None = None
    depth: int
    filters: dict[str, Any] = Field(default_factory=dict, validation_alias="filters_json")
    created_at: datetime


class EvidenceOut(ORMModel):
    id: str
    title: str
    original_filename: str
    content_type: str
    size_bytes: int
    category: str
    status: str
    extracted_text: str
    metadata: dict[str, Any] = Field(default_factory=dict, validation_alias="metadata_json")
    case_id: str | None = None
    uploaded_by_id: str | None = None
    created_at: datetime
    processed_at: datetime | None = None


class EvidenceTrace(BaseModel):
    relationship: dict[str, Any]
    source: dict[str, Any]
    target: dict[str, Any]
    evidence: dict[str, Any] | None = None
    case: dict[str, Any] | None = None


class CameraCreate(BaseModel):
    camera_name: str = Field(min_length=2, max_length=160)
    source_type: str = Field(pattern="^(WEBCAM|VIDEO_FILE|HTTP_STREAM|RTSP)$")
    source_uri: str = Field(min_length=1, max_length=1000)
    location_id: str | None = None
    location_name: str = Field(default="", max_length=240)
    latitude: float | None = None
    longitude: float | None = None
    timezone: str = Field(default="UTC", max_length=64)
    description: str = Field(default="", max_length=10000)
    enabled: bool = True
    case_id: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class CameraUpdate(BaseModel):
    camera_name: str | None = Field(default=None, min_length=2, max_length=160)
    source_type: str | None = Field(default=None, pattern="^(WEBCAM|VIDEO_FILE|HTTP_STREAM|RTSP)$")
    source_uri: str | None = Field(default=None, min_length=1, max_length=1000)
    location_id: str | None = None
    location_name: str | None = Field(default=None, max_length=240)
    latitude: float | None = None
    longitude: float | None = None
    timezone: str | None = Field(default=None, max_length=64)
    description: str | None = Field(default=None, max_length=10000)
    enabled: bool | None = None
    case_id: str | None = None
    metadata: dict[str, Any] | None = None


class CameraOut(ORMModel):
    # `metadata` is a reserved SQLAlchemy declarative attribute, so the ORM
    # column is `metadata_json`. Accept both the field name and the alias so
    # dictionary-built responses keep their payload.
    model_config = ConfigDict(from_attributes=True, populate_by_name=True)

    id: str
    camera_name: str
    source_type: str
    source_uri_masked: str
    location_id: str | None = None
    location_name: str
    latitude: float | None = None
    longitude: float | None = None
    timezone: str
    description: str
    enabled: bool
    record_state: str = "ACTIVE"
    status: str
    last_frame_at: datetime | None = None
    last_detection_at: datetime | None = None
    last_error: str
    detection_count: int
    case_id: str | None = None
    created_by_id: str | None = None
    created_at: datetime
    updated_at: datetime
    metadata: dict[str, Any] = Field(default_factory=dict, validation_alias="metadata_json")


class CameraStatusOut(BaseModel):
    camera_id: str
    status: str
    source_type: str
    last_frame_at: datetime | None = None
    last_detection_at: datetime | None = None
    detection_count: int
    active_detections: int
    last_error: str
    demo_mode: bool = False


class ObservationReviewCreate(BaseModel):
    decision: str = Field(pattern="^(VERIFY|REJECT|ASSOCIATE)$")
    associated_person_id: str | None = None
    notes: str = Field(default="", max_length=10000)


class ObservationReviewOut(ORMModel):
    id: str
    observation_id: str
    reviewer_id: str | None = None
    decision: str
    associated_person_id: str | None = None
    notes: str
    reviewed_at: datetime


class CameraObservationOut(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    id: str
    camera_id: str
    camera_name: str = ""
    timestamp: datetime
    frame_number: int
    bbox: dict[str, int]
    detection_confidence: float | None = None
    confidence_method: str
    evidence_id: str | None = None
    annotated_evidence_id: str | None = None
    clip_evidence_id: str | None = None
    location_id: str | None = None
    location_name: str = ""
    case_id: str | None = None
    review_status: str
    is_simulated: bool
    simulation_label: str
    suggested_person_id: str | None = None
    created_at: datetime
    metadata: dict[str, Any] = Field(default_factory=dict)
    reviews: list[ObservationReviewOut] = Field(default_factory=list)


class PersonReferencePhotoOut(ORMModel):
    id: str
    entity_id: str
    evidence_id: str
    label: str
    notes: str
    created_by_id: str | None = None
    created_at: datetime


class CandidateOut(ORMModel):
    id: str
    evidence_id: str
    candidate_type: str
    value: str
    normalized_value: str
    confidence: float
    source_span: str
    status: str
    entity_id: str | None = None
    created_at: datetime


class GraphNode(BaseModel):
    id: str
    name: str
    entity_type: str
    status: str
    record_state: str
    degree: int
    aliases: list[str] = Field(default_factory=list)
    case_id: str | None = None


class GraphEdge(BaseModel):
    id: str
    source: str
    target: str
    relationship_type: str
    confidence: float
    timestamp: datetime | None = None
    evidence_id: str | None = None
    case_id: str | None = None
    record_state: str


class GraphResponse(BaseModel):
    nodes: list[GraphNode]
    edges: list[GraphEdge]
    depth: int
    center_id: str | None = None


class AnalysisMetric(BaseModel):
    entity_id: str
    name: str
    value: float
    rank: int
    explanation: str


class AnalysisResponse(BaseModel):
    run_id: str
    algorithm: str
    metrics: list[AnalysisMetric]
    communities: list[dict[str, Any]]
    component_count: int
    explanation: str
    created_at: datetime


class TimelinePoint(BaseModel):
    date: str
    relationship_count: int
    disappearance_count: int
    cumulative_relationships: int
    entity_count: int
    event_count: int


class TimelineResponse(BaseModel):
    points: list[TimelinePoint]
    start_date: str | None = None
    end_date: str | None = None
    explanation: str


class MapPoint(BaseModel):
    entity_id: str
    name: str
    entity_type: str
    latitude: float
    longitude: float
    address: str | None = None
    relationship_count: int
    case_id: str | None = None


class MapResponse(BaseModel):
    points: list[MapPoint]
    total_relationships: int
    explanation: str


class SearchResult(BaseModel):
    result_type: str
    id: str
    title: str
    subtitle: str
    entity_type: str | None = None
    case_id: str | None = None
    status: str | None = None


class SearchResponse(BaseModel):
    query: str
    results: list[SearchResult]
    total: int
    explanation: str


class PatternSignal(BaseModel):
    signal_type: str
    title: str
    severity: str
    explanation: str
    entity_ids: list[str] = Field(default_factory=list)
    relationship_ids: list[str] = Field(default_factory=list)
    evidence_ids: list[str] = Field(default_factory=list)
    requires_review: bool = True


class SignalResponse(BaseModel):
    run_id: str
    signals: list[PatternSignal]
    baseline: dict[str, Any]
    explanation: str
    created_at: datetime


class AuditOut(ORMModel):
    id: str
    user_id: str | None = None
    action: str
    resource_type: str | None = None
    resource_id: str | None = None
    details: dict[str, Any] = Field(default_factory=dict, validation_alias="details_json")
    created_at: datetime


class AssistantRequest(BaseModel):
    question: str = Field(min_length=3, max_length=2000)
    case_id: str | None = None


class AssistantResponse(BaseModel):
    answer: str
    citations: list[dict[str, Any]]
    retrieved_entities: list[dict[str, Any]]
    grounded: bool
    disclaimer: str


class SynthesisRequest(BaseModel):
    case_id: str
    title: str = Field(default="Multi-agent intelligence synthesis", min_length=3, max_length=240)


class ReportCreate(BaseModel):
    case_id: str | None = None
    title: str = Field(min_length=3, max_length=240)
    summary: str = Field(default="", max_length=20000)


class ReportOut(ORMModel):
    id: str
    case_id: str | None = None
    title: str
    summary: str
    content: dict[str, Any] = Field(default_factory=dict, validation_alias="content_json")
    version: int
    created_by_id: str | None = None
    created_at: datetime
