from fastapi.testclient import TestClient

from app.main import app


def auth(client: TestClient, username: str = "analyst", password: str = "ChangeMe-Analyst-2026!") -> dict[str, str]:
    response = client.post("/api/v1/auth/login", json={"username": username, "password": password})
    assert response.status_code == 200
    return {"Authorization": f"Bearer {response.json()['access_token']}"}


def test_case_notes_history_and_saved_context() -> None:
    with TestClient(app) as client:
        analyst = auth(client)
        case_id = "CASE-DEMO-2026-001"
        note = client.post(f"/api/v1/cases/{case_id}/notes", headers=analyst, json={"body": "Review synthetic call sequence with the source CDR."})
        assert note.status_code == 201, note.text
        notes = client.get(f"/api/v1/cases/{case_id}/notes", headers=analyst)
        assert notes.status_code == 200
        assert notes.json()[0]["body"].startswith("Review synthetic")
        history = client.get(f"/api/v1/cases/{case_id}/history", headers=analyst)
        assert history.status_code == 200
        saved = client.post("/api/v1/cases/saved-searches", headers=analyst, json={"name": "Aarav calls", "query": "Aarav", "case_id": case_id, "filters": {"entity_type": "PERSON"}})
        assert saved.status_code == 201, saved.text
        assert client.get("/api/v1/cases/saved-searches", headers=analyst).status_code == 200
        view = client.post("/api/v1/cases/saved-views", headers=analyst, json={"name": "Aarav neighborhood", "case_id": case_id, "center_id": "ENT-DEMO-P1001", "depth": 2})
        assert view.status_code == 201, view.text
        assert client.get("/api/v1/cases/saved-views", headers=analyst).status_code == 200
