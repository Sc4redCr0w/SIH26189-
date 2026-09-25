from fastapi.testclient import TestClient

from app.main import app


def test_report_snapshots_versions_and_export() -> None:
    with TestClient(app) as client:
        login = client.post("/api/v1/auth/login", json={"username": "analyst", "password": "ChangeMe-Analyst-2026!"})
        headers = {"Authorization": f"Bearer {login.json()['access_token']}"}
        first = client.post("/api/v1/reports", headers=headers, json={"case_id": "CASE-DEMO-2026-001", "title": "Versioned report", "summary": "Initial summary"})
        second = client.post("/api/v1/reports", headers=headers, json={"case_id": "CASE-DEMO-2026-001", "title": "Versioned report", "summary": "Updated summary"})
        assert first.status_code == 201 and second.status_code == 201
        assert second.json()["version"] == first.json()["version"] + 1
        content = second.json()["content"]
        assert content["graph_snapshot"]["nodes"]
        assert content["timeline_snapshot"]
        export = client.get(f"/api/v1/reports/{second.json()['id']}/export?format=md", headers=headers)
        assert export.status_code == 200
        assert "Versioned report" in export.text
        assert "Content-Disposition" in export.headers
