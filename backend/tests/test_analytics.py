from fastapi.testclient import TestClient

from app.main import app


def auth(client: TestClient) -> dict[str, str]:
    response = client.post("/api/v1/auth/login", json={"username": "analyst", "password": "ChangeMe-Analyst-2026!"})
    assert response.status_code == 200
    return {"Authorization": f"Bearer {response.json()['access_token']}"}


def test_graph_analytics_exposes_structural_metrics_and_explanations() -> None:
    with TestClient(app) as client:
        headers = auth(client)
        for algorithm in ("centrality", "betweenness", "pagerank", "components"):
            response = client.post(f"/api/v1/analytics/network?algorithm={algorithm}&center_id=ENT-DEMO-P1001", headers=headers)
            assert response.status_code == 200, response.text
            payload = response.json()
            assert payload["algorithm"] == algorithm
            assert payload["run_id"]
            assert payload["metrics"]
            assert payload["explanation"]
            assert payload["component_count"] >= 1
        audit = client.get("/api/v1/audit?action=GRAPH_ANALYSIS_RUN", headers=headers)
        assert audit.status_code == 403
