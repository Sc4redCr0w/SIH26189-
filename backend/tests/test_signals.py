from fastapi.testclient import TestClient

from app.main import app


def test_pattern_signals_are_grounded_and_reviewable() -> None:
    with TestClient(app) as client:
        login = client.post("/api/v1/auth/login", json={"username": "analyst", "password": "ChangeMe-Analyst-2026!"})
        headers = {"Authorization": f"Bearer {login.json()['access_token']}"}
        response = client.post("/api/v1/analytics/signals?case_id=CASE-DEMO-2026-001", headers=headers)
        assert response.status_code == 200, response.text
        payload = response.json()
        assert payload["run_id"]
        assert payload["signals"]
        assert payload["baseline"]["relationship_count"] > 0
        assert all(signal["requires_review"] for signal in payload["signals"])
        assert all("conclusion" not in signal["explanation"].lower() or "not" in signal["explanation"].lower() for signal in payload["signals"])
