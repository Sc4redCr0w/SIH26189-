from fastapi.testclient import TestClient

from app.main import app


def test_geographic_view_only_plots_explicit_coordinates() -> None:
    with TestClient(app) as client:
        login = client.post("/api/v1/auth/login", json={"username": "analyst", "password": "ChangeMe-Analyst-2026!"})
        headers = {"Authorization": f"Bearer {login.json()['access_token']}"}
        response = client.get("/api/v1/analytics/geo?case_id=CASE-DEMO-2026-001", headers=headers)
        assert response.status_code == 200, response.text
        payload = response.json()
        assert payload["points"]
        assert all(-90 <= point["latitude"] <= 90 and -180 <= point["longitude"] <= 180 for point in payload["points"])
        assert payload["explanation"]
