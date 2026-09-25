from fastapi.testclient import TestClient

from app.main import app


def test_security_headers_and_unauthenticated_access() -> None:
    with TestClient(app) as client:
        response = client.get("/api/v1/health")
        assert response.status_code == 200
        assert response.headers["x-content-type-options"] == "nosniff"
        assert response.headers["x-frame-options"] == "DENY"
        assert "content-security-policy" in response.headers
        assert client.get("/api/v1/entities").status_code == 401
        assert client.get("/api/v1/audit").status_code == 401
