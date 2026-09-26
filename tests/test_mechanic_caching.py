"""Tests for caching on GET /mechanics (manager-only) and its
invalidation on writes. GET /mechanics/<id> is no longer cached (see
app/blueprints/mechanic/routes.py's module docstring for why), so
there's nothing to test for it here."""

from werkzeug.security import generate_password_hash

from app.extensions import db as _db
from app.models.mechanic import Mechanic
from tests.conftest import make_mechanic_payload, seed_manager


def _manager_headers(cached_client):
    """Bootstrap a manager directly in the database and log in
    through the real API, run against cached_client's app."""
    manager_obj, password = seed_manager(_db)
    login_response = cached_client.post(
        "/mechanics/login", json={"email": manager_obj.email, "password": password}
    )
    token = login_response.json["auth_token"]
    return {"Authorization": f"Bearer {token}"}


def insert_mechanic_directly():
    """Insert a mechanic straight into the database, bypassing the
    API. Because the routes never see this write, they can't clear
    the cache, which makes it a clean way to tell a cached response
    apart from a fresh database query."""
    _db.session.add(
        Mechanic(
            name="Sam Diaz",
            email="sam@example.com",
            phone="555-222-3333",
            salary=58000.00,
            role="mechanic",
            password_hash=generate_password_hash("wrench123"),
        )
    )
    _db.session.commit()


def test_get_mechanics_is_served_from_cache(cached_client):
    """Once the list is cached, a change the API never saw doesn't
    appear in GET /mechanics until the cache is cleared or expires."""
    headers = _manager_headers(cached_client)
    first = cached_client.get("/mechanics", headers=headers).json
    assert len(first) == 1  # just the bootstrapped manager

    insert_mechanic_directly()

    second = cached_client.get("/mechanics", headers=headers).json
    assert len(second) == 1  # still cached; direct insert is invisible


def test_get_mechanics_is_not_cached_when_caching_disabled(client, manager):
    """Control for the test above: with the default (NullCache) test
    config, the same kind of direct insert IS visible immediately."""
    _, manager_headers = manager
    assert len(client.get("/mechanics", headers=manager_headers).json) == 1

    _db.session.add(
        Mechanic(
            name="Sam Diaz",
            email="sam@example.com",
            phone="555-222-3333",
            salary=58000.00,
            role="mechanic",
            password_hash=generate_password_hash("wrench123"),
        )
    )
    _db.session.commit()

    assert len(client.get("/mechanics", headers=manager_headers).json) == 2


def test_create_mechanic_refreshes_cached_list(cached_client):
    """Creating a mechanic clears the cached list, so the new mechanic
    shows up immediately rather than after the timeout."""
    headers = _manager_headers(cached_client)
    assert len(cached_client.get("/mechanics", headers=headers).json) == 1

    cached_client.post("/mechanics", json=make_mechanic_payload(), headers=headers)

    assert len(cached_client.get("/mechanics", headers=headers).json) == 2


def test_update_mechanic_refreshes_cached_list(cached_client):
    """Updating a mechanic clears the cached list, so the list shows
    the new values immediately."""
    headers = _manager_headers(cached_client)
    created = cached_client.post(
        "/mechanics", json=make_mechanic_payload(), headers=headers
    ).json
    mechanic_id = created["id"]

    listing = cached_client.get("/mechanics", headers=headers).json
    entry = next(m for m in listing if m["id"] == mechanic_id)
    assert entry["salary"] == "55000.00"

    cached_client.put(
        f"/mechanics/{mechanic_id}",
        json=make_mechanic_payload(salary=60000.00),
        headers=headers,
    )

    listing = cached_client.get("/mechanics", headers=headers).json
    entry = next(m for m in listing if m["id"] == mechanic_id)
    assert entry["salary"] == "60000.00"


def test_delete_mechanic_refreshes_cached_list(cached_client):
    """Deleting a mechanic clears the cached list, so the deleted
    mechanic disappears from it immediately."""
    headers = _manager_headers(cached_client)
    created = cached_client.post(
        "/mechanics", json=make_mechanic_payload(), headers=headers
    ).json
    mechanic_id = created["id"]

    listing = cached_client.get("/mechanics", headers=headers).json
    assert any(m["id"] == mechanic_id for m in listing)

    cached_client.delete(f"/mechanics/{mechanic_id}", headers=headers)

    listing = cached_client.get("/mechanics", headers=headers).json
    assert not any(m["id"] == mechanic_id for m in listing)
