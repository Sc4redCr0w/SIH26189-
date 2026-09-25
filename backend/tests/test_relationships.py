from fastapi.testclient import TestClient

from app.main import app


def auth(client: TestClient, username: str, password: str) -> dict[str, str]:
    response = client.post("/api/v1/auth/login", json={"username": username, "password": password})
    assert response.status_code == 200
    return {"Authorization": f"Bearer {response.json()['access_token']}"}


def test_relationship_crud_evidence_and_archive_permissions() -> None:
    with TestClient(app) as client:
        admin = auth(client, "admin", "ChangeMe-Admin-2026!")
        analyst = auth(client, "analyst", "ChangeMe-Analyst-2026!")
        source = client.post("/api/v1/entities", headers=admin, json={"name": "Relationship Source", "entity_type": "PERSON"}).json()
        target = client.post("/api/v1/entities", headers=admin, json={"name": "Relationship Target", "entity_type": "PERSON"}).json()
        evidence = client.post("/api/v1/evidence", headers=admin, data={"title": "Relationship source", "category": "CDR"}, files={"file": ("calls.csv", b"source,target\nA,B\n", "text/csv")}).json()
        created = client.post(
            "/api/v1/relationships",
            headers=admin,
            json={"source_id": source["id"], "target_id": target["id"], "relationship_type": "CALLS", "evidence_id": evidence["id"], "timestamp": "2026-09-12T21:32:00Z", "confidence": 0.93, "notes": "Synthetic test edge"},
        )
        assert created.status_code == 201, created.text
        relationship = created.json()
        assert relationship["relationship_type"] == "CALLS"
        assert relationship["evidence_id"] == evidence["id"]

        assert client.patch(f"/api/v1/relationships/{relationship['id']}", headers=analyst, json={"confidence": 0.1}).status_code == 403
        updated = client.patch(f"/api/v1/relationships/{relationship['id']}", headers=admin, json={"confidence": 0.88, "notes": "Reviewed"})
        assert updated.status_code == 200
        assert updated.json()["confidence"] == 0.88
        assert client.delete(f"/api/v1/relationships/{relationship['id']}", headers=admin).status_code == 204
        assert client.get(f"/api/v1/relationships/{relationship['id']}", headers=analyst).status_code == 404
