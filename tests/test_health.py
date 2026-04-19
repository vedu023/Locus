from app.core import health


def test_live_health_returns_ok(client):
    response = client.get("/health/live")

    assert response.status_code == 200
    assert response.json() == {"status": "ok", "service": "locus-api"}


def test_ready_health_returns_ok_when_checks_pass(client, monkeypatch):
    monkeypatch.setattr(health, "check_database", lambda: {"status": "ok"})
    monkeypatch.setattr(health, "check_redis", lambda: {"status": "ok"})

    response = client.get("/health/ready")

    assert response.status_code == 200
    assert response.json()["status"] == "ok"
    assert response.json()["checks"]["database"]["status"] == "ok"


def test_auth_me_uses_dev_identity(client):
    response = client.get("/api/auth/me")

    assert response.status_code == 200
    assert response.json()["user_id"] == "dev-user"
    assert response.json()["auth_mode"] == "dev"
