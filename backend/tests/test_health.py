from fastapi.testclient import TestClient

from app.main import app


client = TestClient(app)


def test_health_reports_running_service() -> None:
    response = client.get("/api/v1/health")

    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "ok"
    assert payload["database"]["status"] == "ok"
    assert payload["environment"] == "development"


def test_readiness_reports_database() -> None:
    response = client.get("/api/v1/health/ready")

    assert response.status_code == 200
    assert response.json()["ready"] is True
