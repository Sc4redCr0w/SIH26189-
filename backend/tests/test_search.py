from fastapi.testclient import TestClient

from app.main import app


def test_unified_search_returns_entity_case_and_evidence_records() -> None:
    with TestClient(app) as client:
        login = client.post("/api/v1/auth/login", json={"username": "analyst", "password": "ChangeMe-Analyst-2026!"})
        headers = {"Authorization": f"Bearer {login.json()['access_token']}"}
        response = client.get("/api/v1/search?q=Aarav&case_id=CASE-DEMO-2026-001", headers=headers)
        assert response.status_code == 200, response.text
        payload = response.json()
        assert payload["total"] >= 2
        assert any(item["result_type"] == "ENTITY" for item in payload["results"])
        assert any(item["result_type"] == "EVIDENCE" for item in payload["results"])
        filtered = client.get("/api/v1/search?q=warehouse&entity_type=LOCATION", headers=headers)
        assert filtered.status_code == 200
        assert all(item["entity_type"] == "LOCATION" for item in filtered.json()["results"] if item["result_type"] == "ENTITY")
