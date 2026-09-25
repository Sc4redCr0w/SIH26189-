from fastapi.testclient import TestClient

from app.main import app


def auth(client: TestClient) -> dict[str, str]:
    response = client.post("/api/v1/auth/login", json={"username": "analyst", "password": "ChangeMe-Analyst-2026!"})
    assert response.status_code == 200
    return {"Authorization": f"Bearer {response.json()['access_token']}"}


def test_relationship_trace_and_evidence_entity_links() -> None:
    with TestClient(app) as client:
        headers = auth(client)
        evidence_id = "EVD-DEMO-FIR001"
        entity_id = "ENT-DEMO-P1001"
        evidence = client.get(f"/api/v1/evidence/{evidence_id}", headers=headers)
        assert evidence.status_code == 200
        assert evidence.json()["extracted_text"]
        linked = client.get(f"/api/v1/evidence/{evidence_id}/entities", headers=headers)
        assert linked.status_code == 200
        assert any(item["id"] == entity_id for item in linked.json())
        reverse = client.get(f"/api/v1/entities/{entity_id}/evidence", headers=headers)
        assert reverse.status_code == 200
        assert any(item["id"] == evidence_id for item in reverse.json())
        trace = client.get("/api/v1/relationships/REL-DEMO-001/trace", headers=headers)
        assert trace.status_code == 200
        payload = trace.json()
        assert payload["source"]["name"] == "Aarav Mehta"
        assert payload["target"]["name"] == "Rohan Kulkarni"
        assert payload["evidence"]["id"] == evidence_id
