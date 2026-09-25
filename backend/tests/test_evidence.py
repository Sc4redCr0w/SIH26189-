from fastapi.testclient import TestClient

from app.main import app


def auth(client: TestClient, username: str, password: str) -> dict[str, str]:
    response = client.post("/api/v1/auth/login", json={"username": username, "password": password})
    assert response.status_code == 200
    return {"Authorization": f"Bearer {response.json()['access_token']}"}


def test_evidence_upload_processing_history_and_access_control() -> None:
    with TestClient(app) as client:
        admin = auth(client, "admin", "ChangeMe-Admin-2026!")
        analyst = auth(client, "analyst", "ChangeMe-Analyst-2026!")
        blocked = client.post(
            "/api/v1/evidence",
            headers=analyst,
            data={"title": "Blocked", "category": "FIR"},
            files={"file": ("blocked.txt", b"not allowed", "text/plain")},
        )
        assert blocked.status_code == 403

        invalid = client.post(
            "/api/v1/evidence",
            headers=admin,
            data={"title": "Invalid", "category": "OTHER"},
            files={"file": ("payload.exe", b"not allowed", "application/octet-stream")},
        )
        assert invalid.status_code == 415

        uploaded = client.post(
            "/api/v1/evidence",
            headers=admin,
            data={"title": "Synthetic CDR extract", "category": "CDR"},
            files={"file": ("cdr.txt", b"source_id,target_id\nA,B\n", "text/plain")},
        )
        assert uploaded.status_code == 201, uploaded.text
        evidence = uploaded.json()
        assert evidence["status"] == "PROCESSED"
        assert evidence["extracted_text"]

        history = client.get(f"/api/v1/evidence/{evidence['id']}", headers=analyst)
        assert history.status_code == 200
        download = client.get(f"/api/v1/evidence/{evidence['id']}/download", headers=analyst)
        assert download.status_code == 200
        assert download.content.startswith(b"source_id,target_id")
