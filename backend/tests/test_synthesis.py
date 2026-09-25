from fastapi.testclient import TestClient

from app.main import app


def test_multi_agent_synthesis_returns_grounded_report_sections() -> None:
    with TestClient(app) as client:
        login = client.post("/api/v1/auth/login", json={"username": "analyst", "password": "ChangeMe-Analyst-2026!"})
        headers = {"Authorization": f"Bearer {login.json()['access_token']}"}
        response = client.post("/api/v1/reports/synthesize", headers=headers, json={"case_id": "CASE-DEMO-2026-001", "title": "Synthetic synthesis"})
        assert response.status_code == 201, response.text
        payload = response.json()
        assert payload["content"]["grounded"] is True
        assert len(payload["content"]["agents"]) == 5
        assert payload["content"]["evidence_ids"]
        assert any(section["title"] == "System limitations" for section in payload["content"]["sections"])
