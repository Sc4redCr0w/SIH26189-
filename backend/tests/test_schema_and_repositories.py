from fastapi.testclient import TestClient

from app.main import app


def login(client: TestClient, username: str, password: str) -> dict[str, object]:
    response = client.post("/api/v1/auth/login", json={"username": username, "password": password})
    assert response.status_code == 200, response.text
    return response.json()


def test_synthetic_graph_has_shared_ids_and_cycles() -> None:
    with TestClient(app) as client:
        session = login(client, "analyst", "ChangeMe-Analyst-2026!")
        headers = {"Authorization": f"Bearer {session['access_token']}"}
        graph = client.get("/api/v1/graph?center_id=ENT-DEMO-P1001&depth=3", headers=headers)
        assert graph.status_code == 200, graph.text
        payload = graph.json()
        assert payload["center_id"] == "ENT-DEMO-P1001"
        assert len(payload["nodes"]) >= 8
        assert len(payload["edges"]) >= 8
        node_ids = {node["id"] for node in payload["nodes"]}
        assert all(edge["source"] in node_ids and edge["target"] in node_ids for edge in payload["edges"])
        assert any(edge["source"] == "ENT-DEMO-P1001" and edge["target"] == "ENT-DEMO-P1002" for edge in payload["edges"])
        assert any(edge["source"] == "ENT-DEMO-P1002" and edge["target"] == "ENT-DEMO-P1001" for edge in payload["edges"])


def test_schema_and_audit_are_available_to_oversight_role() -> None:
    with TestClient(app) as client:
        session = login(client, "auditor", "ChangeMe-Auditor-2026!")
        headers = {"Authorization": f"Bearer {session['access_token']}"}
        response = client.get("/api/v1/audit", headers=headers)
        assert response.status_code == 200
        assert any(item["action"] == "LOGIN_SUCCESS" for item in response.json())
        assert client.get("/api/v1/auth/users", headers=headers).status_code == 403
