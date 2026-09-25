from collections.abc import Generator
from pathlib import Path

from sqlalchemy import create_engine, text
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from .config import get_settings


class Base(DeclarativeBase):
    pass


settings = get_settings()
if settings.is_sqlite:
    database_path = settings.database_url.removeprefix("sqlite:///")
    if database_path and database_path != ":memory:":
        resolved_path = Path(database_path)
        if not resolved_path.is_absolute():
            resolved_path = settings.project_root / resolved_path
        resolved_path.parent.mkdir(parents=True, exist_ok=True)
        engine_url = f"sqlite:///{resolved_path.as_posix()}"
    else:
        engine_url = settings.database_url
    connect_args = {"check_same_thread": False}
else:
    engine_url = settings.database_url
    connect_args = {}

engine = create_engine(
    engine_url,
    connect_args=connect_args,
    pool_pre_ping=True,
)
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False, expire_on_commit=False)


def get_db() -> Generator[Session, None, None]:
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()


def database_status() -> dict[str, str]:
    try:
        with engine.connect() as connection:
            connection.execute(text("SELECT 1"))
        return {"status": "ok", "dialect": engine.dialect.name}
    except Exception as exc:  # pragma: no cover - only used for diagnostics
        return {"status": "error", "dialect": engine.dialect.name, "detail": str(exc)}
