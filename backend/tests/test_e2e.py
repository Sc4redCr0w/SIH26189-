from uuid import uuid4

from fastapi.testclient import TestClient

from app.main import app


def login(client: TestClient, username: str, password: str) -> dict[str, str]:
    response = client.post("/api/v1/auth/login", json={"username": username, "password": password})
    assert response.status_code == 200, response.text
    return {"Authorization": f"Bearer {response.json()['access_token']}"}


def test_end_to_end_admin_to_analyst_intelligence_workflow() -> None:
    with TestClient(app) as client:
        admin = login(client, "admin", "ChangeMe-Admin-2026!")
        suffix = uuid4().hex[:6]
        case = client.post("/api/v1/cases", headers=admin, json={"case_number": f"CASE-E2E-{suffix}", "title": "Synthetic end-to-end review", "description": "Fictional integration scenario"}).json()
        evidence = client.post("/api/v1/evidence", headers=admin, data={"title": "E2E FIR text", "category": "FIR", "case_id": case["id"]}, files={"file": ("e2e.txt", b"Aarav Mehta met Rohan Kulkarni near Warehouse 9. Rohan Kulkarni used +919820041122.", "text/plain")}).json()
        candidates = client.post(f"/api/v1/evidence/{evidence['id']}/extract", headers=admin).json()
        assert candidates
        relationship_candidate = next(item for item in candidates if item["candidate_type"] == "RELATIONSHIP")
        approved = client.post(f"/api/v1/extractions/candidates/{relationship_candidate['id']}/approve", headers=admin)
        assert approved.status_code == 200, approved.text

        analyst = login(client, "analyst", "ChangeMe-Analyst-2026!")
        graph = client.get("/api/v1/graph?center_id=ENT-DEMO-P1001&depth=2", headers=analyst)
        assert graph.status_code == 200 and graph.json()["nodes"]
        analysis = client.post("/api/v1/analytics/network?algorithm=centrality&center_id=ENT-DEMO-P1001", headers=analyst)
        assert analysis.status_code == 200 and analysis.json()["metrics"]
        answer = client.post("/api/v1/assistant/query", headers=analyst, json={"question": "What evidence supports Aarav Mehta?"})
        assert answer.status_code == 200 and answer.json()["grounded"]
        report = client.post("/api/v1/reports/synthesize", headers=analyst, json={"case_id": case["id"], "title": "E2E synthesis"})
        assert report.status_code == 201 and report.json()["content"]["grounded"]
        assert client.get("/api/v1/audit?action=REPORT_GENERATED", headers=admin).status_code == 200
