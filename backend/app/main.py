from contextlib import asynccontextmanager
from datetime import UTC, datetime

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from . import __version__
from .bootstrap import initialize_database
from .camera_manager import camera_manager
from .config import get_settings
from .db import database_status
from .middleware import LoginRateLimitMiddleware, SecurityHeadersMiddleware
from .routers import (
    analytics,
    assistant,
    audit,
    auth,
    cases,
    cameras,
    entities,
    evidence,
    extractions,
    imports,
    graph,
    relationships,
    reports,
    search,
)

settings = get_settings()


@asynccontextmanager
async def lifespan(_: FastAPI):
    initialize_database()
    if settings.camera_auto_start:
        camera_manager.start_all()
    try:
        yield
    finally:
        camera_manager.stop_all()


app = FastAPI(
    title=settings.app_name,
    version=__version__,
    description="Evidence-first criminal network intelligence API.",
    docs_url="/docs",
    redoc_url="/redoc",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://127.0.0.1:5173", "http://localhost:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.add_middleware(LoginRateLimitMiddleware, limit=60, window_seconds=60)
app.add_middleware(SecurityHeadersMiddleware)

for router in (
    auth.router,
    entities.router,
    relationships.router,
    cases.saved_router,
    cases.router,
    cameras.router,
    evidence.router,
    extractions.router,
    imports.router,
    graph.router,
    analytics.router,
    assistant.router,
    reports.router,
    search.router,
    audit.router,
):
    app.include_router(router, prefix=settings.api_prefix)


@app.get("/")
def root() -> dict[str, str]:
    return {
        "service": settings.app_name,
        "status": "running",
        "docs": "/docs",
        "health": f"{settings.api_prefix}/health",
    }


@app.get(f"{settings.api_prefix}/health")
def health() -> dict[str, object]:
    database = database_status()
    return {
        "status": "ok" if database["status"] == "ok" else "degraded",
        "service": settings.app_name,
        "version": __version__,
        "environment": settings.environment,
        "timestamp": datetime.now(UTC).isoformat(),
        "database": database,
        "neo4j": "not_configured" if not settings.neo4j_enabled else "configured",
        "ollama": "not_configured" if not settings.ollama_enabled else "configured",
    }


@app.get(f"{settings.api_prefix}/health/ready")
def readiness() -> dict[str, object]:
    database = database_status()
    ready = database["status"] == "ok"
    return {"ready": ready, "database": database}


frontend_dist = settings.project_root / "frontend" / "dist"
if frontend_dist.is_dir():
    app.mount("/", StaticFiles(directory=frontend_dist, html=True), name="frontend")
