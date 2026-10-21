"""Tests for the /health monitoring endpoint."""

from app.extensions import db


def test_health_check_returns_ok_when_database_reachable(client):
    """With the test suite's normal in-memory SQLite database up, the
    health check should report 200/ok and echo a request ID header."""
    response = client.get("/health")

    assert response.status_code == 200
    assert response.json == {"status": "ok"}
    assert "X-Request-ID" in response.headers


def test_health_check_returns_503_when_database_unreachable(client, monkeypatch):
    """If the database query itself fails, the route should report a
    503 with an error detail, not a generic unhandled 500."""
    def _broken_execute(*_args, **_kwargs):
        raise RuntimeError("simulated database outage")

    monkeypatch.setattr(db.session, "execute", _broken_execute)

    response = client.get("/health")

    assert response.status_code == 503
    assert response.json["status"] == "error"
    assert "simulated database outage" in response.json["detail"]
