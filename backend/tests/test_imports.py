from uuid import uuid4

from fastapi.testclient import TestClient

from app.main import app


def test_synthetic_csv_import_creates_reviewable_records() -> None:
    with TestClient(app) as client:
        login = client.post("/api/v1/auth/login", json={"username": "admin", "password": "ChangeMe-Admin-2026!"})
        headers = {"Authorization": f"Bearer {login.json()['access_token']}"}
        suffix = uuid4().hex[:8]
        source = f"P-{suffix}-1"
        target = f"P-{suffix}-2"
        csv_data = f"id,name,entity_type\n{source},Import Alpha {suffix},PERSON\n{target},Import Beta {suffix},PERSON\nsource_id,target_id,relationship_type\n{source},{target},CALLS\n".encode()
        response = client.post("/api/v1/imports/csv", headers=headers, data={"title": "Synthetic import", "category": "CDR"}, files={"file": ("batch.csv", csv_data, "text/csv")})
        assert response.status_code == 201, response.text
        payload = response.json()
        assert payload["rows"] == 4
        assert payload["entities_created"] == 2
        assert payload["relationships_created"] == 1
        assert payload["status"] == "REVIEW_REQUIRED"
