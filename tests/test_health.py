"""Tests for the /health and /health/db monitoring endpoints."""

from app.extensions import db


def _broken_execute(*_args, **_kwargs):
    """Stand-in for db.session.execute that simulates a database outage."""
    raise RuntimeError("simulated database outage")


def test_health_check_returns_ok(client):
    """/health should report 200/ok and echo a request ID header."""
    response = client.get("/health")

    assert response.status_code == 200
    assert response.json == {"status": "ok"}
    assert "X-Request-ID" in response.headers


def test_health_check_does_not_touch_database(client, monkeypatch):
    """/health must stay up and never query the database.

    An uptime monitor polls this route every few minutes, so a query here
    would keep a scale-to-zero database awake around the clock. Making the
    database raise on any query proves the route does not use it.
    """
    monkeypatch.setattr(db.session, "execute", _broken_execute)

    response = client.get("/health")

    assert response.status_code == 200
    assert response.json == {"status": "ok"}


def test_health_db_returns_ok_when_database_reachable(client):
    """With the test suite's normal in-memory SQLite database up, the
    deeper check should report 200/ok and echo a request ID header."""
    response = client.get("/health/db")

    assert response.status_code == 200
    assert response.json == {"status": "ok"}
    assert "X-Request-ID" in response.headers


def test_health_db_returns_503_when_database_unreachable(client, monkeypatch):
    """If the database query itself fails, /health/db should report a
    503 with an error detail, not a generic unhandled 500."""
    monkeypatch.setattr(db.session, "execute", _broken_execute)

    response = client.get("/health/db")

    assert response.status_code == 503
    assert response.json["status"] == "error"
    assert "simulated database outage" in response.json["detail"]
