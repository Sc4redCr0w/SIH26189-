from fastapi.testclient import TestClient

from app.main import app


def session(client: TestClient, username: str, password: str) -> tuple[str, dict[str, str]]:
    response = client.post("/api/v1/auth/login", json={"username": username, "password": password})
    assert response.status_code == 200, response.text
    return response.json()["access_token"], {"Authorization": f"Bearer {response.json()['access_token']}"}


def test_entity_crud_duplicate_warning_and_archive() -> None:
    with TestClient(app) as client:
        _, admin_headers = session(client, "admin", "ChangeMe-Admin-2026!")
        created = client.post(
            "/api/v1/entities",
            headers=admin_headers,
            json={"name": "A. Mehta", "entity_type": "PERSON", "aliases": ["Aarav M."]},
        )
        assert created.status_code == 201, created.text
        entity = created.json()
        duplicates = client.get(f"/api/v1/entities/{entity['id']}/duplicates", headers=admin_headers)
        assert duplicates.status_code == 200
        assert any(item["entity_id"] == "ENT-DEMO-P1001" for item in duplicates.json())

        analyst_token, analyst_headers = session(client, "analyst", "ChangeMe-Analyst-2026!")
        assert client.patch(f"/api/v1/entities/{entity['id']}", headers=analyst_headers, json={"status": "ATTENTION"}).status_code == 403
        assert client.delete(f"/api/v1/entities/{entity['id']}", headers=admin_headers).status_code == 204
        assert client.get(f"/api/v1/entities/{entity['id']}", headers=admin_headers).status_code == 404
        merge_source = client.post("/api/v1/entities", headers=admin_headers, json={"name": "Merge Source", "entity_type": "PERSON"})
        merge_target = client.post("/api/v1/entities", headers=admin_headers, json={"name": "Merge Target", "entity_type": "PERSON"})
        assert merge_source.status_code == 201 and merge_target.status_code == 201
        merge = client.post(f"/api/v1/entities/{merge_source.json()['id']}/merge", headers=admin_headers, json={"target_entity_id": merge_target.json()["id"], "reason": "Synthetic identity reconciliation", "confirm": True})
        assert merge.status_code == 200, merge.text
        assert merge.json()["archived_entity_id"] == merge_source.json()["id"]
        assert analyst_token
