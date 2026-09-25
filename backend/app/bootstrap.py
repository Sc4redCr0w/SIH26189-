from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path
import shutil

from sqlalchemy import insert, select
from sqlalchemy.orm import Session

from .config import get_settings
from .db import Base, SessionLocal, engine
from .models import Case, Entity, Evidence, Relationship, User, entity_evidence
from .security import hash_password


def create_schema() -> None:
    Base.metadata.create_all(bind=engine)


def seed_users(db: Session) -> None:
    settings = get_settings()
    seeds = [
        (settings.seed_admin_username, "Platform administrator", settings.seed_admin_password, "ADMIN"),
        (settings.seed_analyst_username, "Investigations analyst", settings.seed_analyst_password, "ANALYST"),
        (settings.seed_auditor_username, "Audit supervisor", settings.seed_auditor_password, "AUDITOR"),
    ]
    for username, display_name, password, role in seeds:
        existing = db.scalar(select(User).where(User.username == username))
        if existing is None:
            db.add(
                User(
                    username=username,
                    display_name=display_name,
                    password_hash=hash_password(password),
                    role=role,
                )
            )
    db.commit()


def seed_demo_data(db: Session) -> None:
    """Create one clearly fictional graph so the local UI is explorable on first run."""
    if db.scalar(select(Entity).where(Entity.name == "Aarav Mehta")):
        evidence = db.get(Evidence, "EVD-DEMO-FIR001")
        if evidence:
            location = db.get(Entity, "ENT-DEMO-LOC1001")
            if location and not (location.metadata_json or {}).get("latitude"):
                location.metadata_json = {"address": "Sector 18, Navi Mumbai", "latitude": 18.78, "longitude": 73.02, "synthetic": True}
            for entity_id in ("ENT-DEMO-P1001", "ENT-DEMO-P1002", "ENT-DEMO-P1003", "ENT-DEMO-P1004", "ENT-DEMO-PH1001", "ENT-DEMO-VE1001", "ENT-DEMO-LOC1001", "ENT-DEMO-ORG1001", "ENT-DEMO-EVT1001"):
                link = db.scalar(select(entity_evidence).where(entity_evidence.entity_id == entity_id, entity_evidence.evidence_id == evidence.id))
                if link is None:
                    db.execute(insert(entity_evidence).values(entity_id=entity_id, evidence_id=evidence.id, relation="MENTIONED_IN"))
            db.commit()
        return
    settings = get_settings()
    admin = db.scalar(select(User).where(User.role == "ADMIN"))
    if admin is None:
        return

    case = Case(
        id="CASE-DEMO-2026-001",
        case_number="CASE-2026-001",
        title="Synthetic harbor network review",
        description="A fictional dataset for end-to-end demonstration only.",
        status="ACTIVE",
        priority="HIGH",
        created_by_id=admin.id,
    )
    db.add(case)
    db.flush()

    def entity(entity_id: str, name: str, entity_type: str, status: str = "UNKNOWN", aliases: list[str] | None = None) -> Entity:
        item = Entity(
            id=entity_id,
            name=name,
            normalized_name=name.casefold(),
            entity_type=entity_type,
            aliases=aliases or [],
            status=status,
            case_id=case.id,
            created_by_id=admin.id,
            notes="Synthetic demonstration record; not a real person or organization.",
        )
        db.add(item)
        return item

    aarav = entity("ENT-DEMO-P1001", "Aarav Mehta", "PERSON", aliases=["A. Mehta", "Aarav M."])
    rohan = entity("ENT-DEMO-P1002", "Rohan Kulkarni", "PERSON", aliases=["R. Kulkarni"])
    meera = entity("ENT-DEMO-P1003", "Meera Shah", "PERSON", "RELEVANT", ["M. Shah"])
    devika = entity("ENT-DEMO-P1004", "Devika Rao", "PERSON", aliases=["D. Rao"])
    phone = entity("ENT-DEMO-PH1001", "+919820041122", "PHONE")
    vehicle = entity("ENT-DEMO-VE1001", "MH12AB4821", "VEHICLE")
    location = entity("ENT-DEMO-LOC1001", "Warehouse 9", "LOCATION")
    organization = entity("ENT-DEMO-ORG1001", "Meridian Logistics", "ORGANIZATION")
    event = entity("ENT-DEMO-EVT1001", "Warehouse 9 night transfer", "EVENT")
    location.metadata_json = {"address": "Sector 18, Navi Mumbai", "latitude": 18.78, "longitude": 73.02, "synthetic": True}
    db.flush()

    source_path = settings.project_root / "datasets" / "reports" / "FIR_001.txt"
    upload_path = settings.resolved_upload_dir / "demo-FIR_001.txt"
    upload_path.parent.mkdir(parents=True, exist_ok=True)
    if source_path.is_file():
        shutil.copyfile(source_path, upload_path)
    evidence = Evidence(
        id="EVD-DEMO-FIR001",
        title="Synthetic FIR / network review",
        original_filename="FIR_001.txt",
        stored_filename=upload_path.name,
        content_type="text/plain",
        size_bytes=upload_path.stat().st_size if upload_path.is_file() else 0,
        category="FIR",
        status="PROCESSED",
        storage_path=str(upload_path.resolve()),
        extracted_text=source_path.read_text(encoding="utf-8") if source_path.is_file() else "",
        metadata_json={"synthetic": True, "source_path": "datasets/reports/FIR_001.txt"},
        case_id=case.id,
        uploaded_by_id=admin.id,
        processed_at=datetime.now(UTC),
    )
    db.add(evidence)
    db.flush()

    def relationship(rel_id: str, source: Entity, target: Entity, rel_type: str, timestamp: datetime | None, confidence: float = 0.92) -> None:
        db.add(
            Relationship(
                id=rel_id,
                source_id=source.id,
                target_id=target.id,
                relationship_type=rel_type,
                timestamp=timestamp,
                evidence_id=evidence.id,
                case_id=case.id,
                confidence=confidence,
                notes="Synthetic relationship; requires analyst review before operational use.",
                created_by_id=admin.id,
            )
        )

    base = datetime(2026, 9, 12, 16, 2, tzinfo=UTC)
    relationship("REL-DEMO-001", aarav, rohan, "CALLS", base, .98)
    relationship("REL-DEMO-002", rohan, meera, "CALLS", base.replace(hour=17), .95)
    relationship("REL-DEMO-003", meera, devika, "ASSOCIATED_WITH", base.replace(hour=18), .86)
    relationship("REL-DEMO-004", aarav, vehicle, "OWNS", base.replace(hour=19), .99)
    relationship("REL-DEMO-005", rohan, phone, "USES", base.replace(hour=20), .97)
    relationship("REL-DEMO-006", aarav, location, "VISITED", base.replace(hour=21), .9)
    relationship("REL-DEMO-007", aarav, organization, "WORKS_FOR", base.replace(hour=22), .88)
    relationship("REL-DEMO-008", meera, event, "PRESENT_AT", base.replace(hour=23), .84)
    relationship("REL-DEMO-009", devika, rohan, "CALLS", base.replace(day=13, hour=9), .81)
    relationship("REL-DEMO-010", rohan, aarav, "CALLS", base.replace(day=14, hour=11), .94)
    for item in (aarav, rohan, meera, devika, phone, vehicle, location, organization, event):
        db.execute(insert(entity_evidence).values(entity_id=item.id, evidence_id=evidence.id, relation="MENTIONED_IN"))
    db.commit()


def initialize_database() -> None:
    create_schema()
    with SessionLocal() as db:
        seed_users(db)
        seed_demo_data(db)
