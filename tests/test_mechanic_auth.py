"""Tests for mechanic login."""

from app.extensions import db as _db
from tests.conftest import make_mechanic_payload, seed_manager


def test_login_returns_token_for_valid_credentials(client, db):
    """POST /mechanics/login should return 200 and a JWT when the
    email and password match a registered mechanic account."""
    manager_obj, password = seed_manager(db)

    response = client.post(
        "/mechanics/login",
        json={"email": manager_obj.email, "password": password},
    )

    assert response.status_code == 200
    assert "auth_token" in response.json


def test_login_rejects_wrong_password(client, db):
    """POST /mechanics/login should return 401 for a registered email
    with an incorrect password."""
    manager_obj, _ = seed_manager(db)

    response = client.post(
        "/mechanics/login",
        json={"email": manager_obj.email, "password": "wrong-password"},
    )

    assert response.status_code == 401


def test_login_rejects_unknown_email(client):
    """POST /mechanics/login should return 401 for an email that
    isn't registered at all, with the same message as a wrong
    password."""
    response = client.post(
        "/mechanics/login", json={"email": "nobody@example.com", "password": "whatever"}
    )

    assert response.status_code == 401


def test_login_rejects_missing_fields(client, db):
    """POST /mechanics/login should return a 400 when password is
    missing from the request body."""
    manager_obj, _ = seed_manager(db)

    response = client.post("/mechanics/login", json={"email": manager_obj.email})

    assert response.status_code == 400


def test_password_is_never_returned_in_responses(client, manager):
    """A mechanic's plaintext password and hashed password must never
    appear in any serialized response."""
    _, manager_headers = manager

    response = client.post(
        "/mechanics", json=make_mechanic_payload(), headers=manager_headers
    )

    assert "password" not in response.json
    assert "password_hash" not in response.json
