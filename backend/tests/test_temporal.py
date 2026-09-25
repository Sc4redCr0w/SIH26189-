from fastapi.testclient import TestClient

from app.main import app


def test_timeline_returns_dated_relationship_activity() -> None:
    with TestClient(app) as client:
        login = client.post("/api/v1/auth/login", json={"username": "analyst", "password": "ChangeMe-Analyst-2026!"})
        headers = {"Authorization": f"Bearer {login.json()['access_token']}"}
        response = client.get("/api/v1/analytics/timeline?case_id=CASE-DEMO-2026-001", headers=headers)
        assert response.status_code == 200, response.text
        payload = response.json()
        assert payload["points"]
        assert payload["points"][-1]["cumulative_relationships"] >= payload["points"][0]["relationship_count"]
        assert payload["explanation"]
