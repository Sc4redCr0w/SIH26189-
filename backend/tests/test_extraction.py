from fastapi.testclient import TestClient

from app.main import app


def headers(client: TestClient, username: str = "admin", password: str = "ChangeMe-Admin-2026!") -> dict[str, str]:
    response = client.post("/api/v1/auth/login", json={"username": username, "password": password})
    assert response.status_code == 200
    return {"Authorization": f"Bearer {response.json()['access_token']}"}


def test_extraction_creates_review_queue_and_requires_approval() -> None:
    with TestClient(app) as client:
        admin = headers(client)
        upload = client.post(
            "/api/v1/evidence",
            headers=admin,
            data={"title": "Extraction review source", "category": "FIR"},
            files={"file": ("review.txt", b"Aarav Mehta met Rohan Kulkarni near Warehouse 9. Rohan Kulkarni used +919820041122 on 12/09/2026.", "text/plain")},
        )
        assert upload.status_code == 201, upload.text
        evidence_id = upload.json()["id"]
        extracted = client.post(f"/api/v1/evidence/{evidence_id}/extract", headers=admin)
        assert extracted.status_code == 200, extracted.text
        candidates = extracted.json()
        assert any(item["candidate_type"] == "PERSON" for item in candidates)
        assert any(item["candidate_type"] == "RELATIONSHIP" for item in candidates)

        queue = client.get(f"/api/v1/extractions/candidates?evidence_id={evidence_id}&status=PENDING", headers=admin)
        assert queue.status_code == 200
        candidate_id = queue.json()[0]["id"]
        approved = client.post(f"/api/v1/extractions/candidates/{candidate_id}/approve", headers=admin)
        assert approved.status_code == 200, approved.text
        assert approved.json()["candidate"]["status"] == "APPROVED"

        analyst = headers(client, "analyst", "ChangeMe-Analyst-2026!")
        pending = client.get(f"/api/v1/extractions/candidates?evidence_id={evidence_id}&status=PENDING", headers=analyst)
        assert pending.status_code == 200
        if pending.json():
            assert client.post(f"/api/v1/extractions/candidates/{pending.json()[0]['id']}/reject", headers=analyst).status_code == 403
