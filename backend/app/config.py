from functools import lru_cache
from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "Criminal Network Intelligence Platform"
    environment: str = "development"
    debug: bool = False
    host: str = "127.0.0.1"
    port: int = 8000
    api_prefix: str = "/api/v1"

    database_url: str = "sqlite:///./backend/data/cni.db"
    upload_dir: Path = Path("./backend/storage/uploads")

    neo4j_enabled: bool = False
    neo4j_uri: str = "bolt://127.0.0.1:7687"
    neo4j_user: str = "neo4j"
    neo4j_password: str = "change-me"

    ollama_enabled: bool = False
    ollama_url: str = "http://127.0.0.1:11434"
    ollama_model: str = "llama3.2:3b"

    camera_detection_enabled: bool = True
    camera_demo_mode: bool = False
    camera_detection_cooldown_seconds: float = 10.0
    camera_frame_interval_seconds: float = 0.08
    camera_evidence_pre_event_frames: int = 2
    camera_evidence_post_event_frames: int = 2
    camera_evidence_clip_enabled: bool = False
    camera_auto_start: bool = False

    jwt_secret: str = Field(default="development-only-change-me", min_length=16)
    jwt_algorithm: str = "HS256"
    access_token_minutes: int = 60

    seed_admin_username: str = "admin"
    seed_admin_password: str = "ChangeMe-Admin-2026!"
    seed_analyst_username: str = "analyst"
    seed_analyst_password: str = "ChangeMe-Analyst-2026!"
    seed_auditor_username: str = "auditor"
    seed_auditor_password: str = "ChangeMe-Auditor-2026!"

    model_config = SettingsConfigDict(
        env_file=("../.env", ".env"),
        env_prefix="CNI_",
        extra="ignore",
    )

    @property
    def project_root(self) -> Path:
        return Path(__file__).resolve().parents[2]

    @property
    def resolved_upload_dir(self) -> Path:
        return self.upload_dir if self.upload_dir.is_absolute() else self.project_root / self.upload_dir

    @property
    def is_sqlite(self) -> bool:
        return self.database_url.startswith("sqlite")


@lru_cache
def get_settings() -> Settings:
    return Settings()
