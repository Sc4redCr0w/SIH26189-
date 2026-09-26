from fastapi.testclient import TestClient

from app.main import app


def auth(client: TestClient, username: str, password: str) -> dict[str, str]:
    response = client.post("/api/v1/auth/login", json={"username": username, "password": password})
    assert response.status_code == 200, response.text
    return {"Authorization": f"Bearer {response.json()['access_token']}"}


def test_camera_crud_authorization_and_graph_projection() -> None:
    with TestClient(app) as client:
        admin = auth(client, "admin", "ChangeMe-Admin-2026!")
        analyst = auth(client, "analyst", "ChangeMe-Analyst-2026!")
        payload = {"camera_name": "Test Main Gate", "source_type": "WEBCAM", "source_uri": "0", "location_name": "Test Gate Location", "timezone": "Asia/Kolkata", "description": "Synthetic camera test"}
        blocked = client.post("/api/v1/cameras", headers=analyst, json=payload)
        assert blocked.status_code == 403
        created = client.post("/api/v1/cameras", headers=admin, json=payload)
        assert created.status_code == 201, created.text
        camera = created.json()
        assert camera["source_uri_masked"] == "0"
        assert camera["record_state"] == "ACTIVE"
        assert client.get("/api/v1/cameras", headers=analyst).status_code == 200
        assert client.get(f"/api/v1/cameras/{camera['id']}", headers=analyst).status_code == 200
        graph = client.get(f"/api/v1/graph?center_id={camera['id']}", headers=analyst)
        assert graph.status_code == 200
        assert any(node["id"] == camera["id"] and node["entity_type"] == "CAMERA" for node in graph.json()["nodes"])
        invalid = client.post("/api/v1/cameras", headers=admin, json={**payload, "source_type": "HTTP_STREAM", "source_uri": "not-a-url"})
        assert invalid.status_code == 422
        assert client.get(f"/api/v1/cameras/{camera['id']}/latest-frame").status_code == 401
        archived = client.delete(f"/api/v1/cameras/{camera['id']}", headers=admin)
        assert archived.status_code == 204
        assert client.get(f"/api/v1/cameras/{camera['id']}", headers=admin).status_code == 404


def test_camera_review_routes_are_readable_and_not_automatically_identified() -> None:
    with TestClient(app) as client:
        analyst = auth(client, "analyst", "ChangeMe-Analyst-2026!")
        response = client.get("/api/v1/cameras/observations/all", headers=analyst)
        assert response.status_code == 200
        assert isinstance(response.json(), list)
        missing = client.post("/api/v1/cameras/observations/OBS-NOT-REAL/review", headers=analyst, json={"decision": "ASSOCIATE", "associated_person_id": "ENT-DEMO-P1001"})
        assert missing.status_code == 404
