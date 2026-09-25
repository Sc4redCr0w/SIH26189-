from uuid import uuid4

from fastapi.testclient import TestClient

from app.main import app


def test_new_entities_can_be_searched_and_graphed_after_relationship_creation() -> None:
    with TestClient(app) as client:
        login = client.post("/api/v1/auth/login", json={"username": "admin", "password": "ChangeMe-Admin-2026!"})
        assert login.status_code == 200
        headers = {"Authorization": f"Bearer {login.json()['access_token']}"}
        suffix = uuid4().hex[:8]
        first_name = f"Fresh Alpha {suffix}"
        second_name = f"Fresh Beta {suffix}"
        first = client.post("/api/v1/entities", headers=headers, json={"name": first_name, "entity_type": "PERSON"})
        second = client.post("/api/v1/entities", headers=headers, json={"name": second_name, "entity_type": "PERSON"})
        assert first.status_code == 201
        assert second.status_code == 201
        first_id = first.json()["id"]
        second_id = second.json()["id"]
        relationship = client.post(
            "/api/v1/relationships",
            headers=headers,
            json={"source_id": first_id, "target_id": second_id, "relationship_type": "ASSOCIATED_WITH"},
        )
        assert relationship.status_code == 201
        search = client.get(f"/api/v1/entities?q={first_name}", headers=headers)
        assert search.status_code == 200
        assert any(item["id"] == first_id for item in search.json())
        graph = client.get(f"/api/v1/graph?center_id={first_id}&depth=2", headers=headers)
        assert graph.status_code == 200
        payload = graph.json()
        assert {first_id, second_id}.issubset({node["id"] for node in payload["nodes"]})
        assert any(edge["source"] == first_id and edge["target"] == second_id for edge in payload["edges"])
