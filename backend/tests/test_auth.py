from fastapi.testclient import TestClient

from app.main import app


def login(client: TestClient, username: str, password: str) -> dict[str, object]:
    response = client.post("/api/v1/auth/login", json={"username": username, "password": password})
    assert response.status_code == 200, response.text
    return response.json()


def auth_headers(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def test_roles_are_enforced_on_the_backend() -> None:
    with TestClient(app) as client:
        admin = login(client, "admin", "ChangeMe-Admin-2026!")
        analyst = login(client, "analyst", "ChangeMe-Analyst-2026!")

        me = client.get("/api/v1/auth/me", headers=auth_headers(str(analyst["access_token"])))
        assert me.status_code == 200
        assert me.json()["role"] == "ANALYST"

        blocked = client.post(
            "/api/v1/entities",
            headers=auth_headers(str(analyst["access_token"])),
            json={"name": "Read-only probe", "entity_type": "PERSON"},
        )
        assert blocked.status_code == 403

        created = client.post(
            "/api/v1/entities",
            headers=auth_headers(str(admin["access_token"])),
            json={"name": "Auth test entity", "entity_type": "PERSON"},
        )
        assert created.status_code == 201, created.text


def test_logout_revokes_the_access_token() -> None:
    with TestClient(app) as client:
        session = login(client, "analyst", "ChangeMe-Analyst-2026!")
        headers = auth_headers(str(session["access_token"]))
        assert client.post("/api/v1/auth/logout", headers=headers).status_code == 204
        assert client.get("/api/v1/auth/me", headers=headers).status_code == 401
