from fastapi.testclient import TestClient

from app.main import app


def auth(client: TestClient) -> dict[str, str]:
    response = client.post("/api/v1/auth/login", json={"username": "analyst", "password": "ChangeMe-Analyst-2026!"})
    assert response.status_code == 200
    return {"Authorization": f"Bearer {response.json()['access_token']}"}


def test_assistant_returns_grounded_citations_and_handles_missing_context() -> None:
    with TestClient(app) as client:
        headers = auth(client)
        grounded = client.post("/api/v1/assistant/query", headers=headers, json={"question": "What evidence supports Aarav Mehta and Rohan Kulkarni?"})
        assert grounded.status_code == 200, grounded.text
        payload = grounded.json()
        assert payload["grounded"] is True
        assert payload["citations"]
        assert payload["retrieved_entities"]
        assert "Evidence" in payload["answer"]
        multihop = client.post("/api/v1/assistant/query", headers=headers, json={"question": "Show Aarav Mehta's second-degree connections"})
        assert multihop.status_code == 200
        assert len(multihop.json()["retrieved_entities"]) >= 3
        missing = client.post("/api/v1/assistant/query", headers=headers, json={"question": "Tell me about a person who is not in the graph"})
        assert missing.status_code == 200
        assert missing.json()["grounded"] is False
        assert missing.json()["citations"] == []
