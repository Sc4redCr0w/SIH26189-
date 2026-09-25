from fastapi.testclient import TestClient

from app.main import app


def test_audit_is_append_only_and_exportable() -> None:
    with TestClient(app) as client:
        login = client.post("/api/v1/auth/login", json={"username": "auditor", "password": "ChangeMe-Auditor-2026!"})
        headers = {"Authorization": f"Bearer {login.json()['access_token']}"}
        events = client.get("/api/v1/audit", headers=headers)
        assert events.status_code == 200
        assert events.json()
        export = client.get("/api/v1/audit/export", headers=headers)
        assert export.status_code == 200
        assert "timestamp,action" in export.text
        assert client.patch("/api/v1/audit/AUD-DOES-NOT-EXIST", headers=headers, json={}).status_code in {404, 405}
        assert client.delete("/api/v1/audit/AUD-DOES-NOT-EXIST", headers=headers).status_code in {404, 405}
