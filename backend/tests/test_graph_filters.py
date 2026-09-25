from fastapi.testclient import TestClient

from app.main import app


def test_graph_filters_depth_relationship_type_and_date() -> None:
    with TestClient(app) as client:
        login = client.post("/api/v1/auth/login", json={"username": "analyst", "password": "ChangeMe-Analyst-2026!"})
        headers = {"Authorization": f"Bearer {login.json()['access_token']}"}
        calls = client.get("/api/v1/graph?center_id=ENT-DEMO-P1001&depth=1&relationship_types=CALLS", headers=headers)
        assert calls.status_code == 200
        assert calls.json()["edges"]
        assert all(edge["relationship_type"] == "CALLS" for edge in calls.json()["edges"])
        dated = client.get("/api/v1/graph?center_id=ENT-DEMO-P1001&depth=3&start_date=2026-09-13T00:00:00Z&end_date=2026-09-14T23:59:59Z", headers=headers)
        assert dated.status_code == 200
        assert all(edge["timestamp"] is None or "2026-09-13" <= edge["timestamp"][:10] <= "2026-09-14" for edge in dated.json()["edges"])
