"""Tests for caching on GET /mechanics (manager-only, paginated) and
its invalidation on writes."""

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
    assert first["total"] == 1  # just the bootstrapped manager

    insert_mechanic_directly()

    second = cached_client.get("/mechanics", headers=headers).json
    assert second["total"] == 1  # still cached; direct insert is invisible


def test_get_mechanics_is_not_cached_when_caching_disabled(client, manager):
    """Control for the test above: with the default (NullCache) test
    config, the same kind of direct insert IS visible immediately."""
    _, manager_headers = manager
    assert client.get("/mechanics", headers=manager_headers).json["total"] == 1

    insert_mechanic_directly()

    assert client.get("/mechanics", headers=manager_headers).json["total"] == 2


def test_create_mechanic_refreshes_cached_list(cached_client):
    """Creating a mechanic clears the ENTIRE cache (cache.clear()),
    so the new mechanic shows up immediately rather than after the
    timeout, on every cached page."""
    headers = _manager_headers(cached_client)
    assert cached_client.get("/mechanics", headers=headers).json["total"] == 1

    cached_client.post("/mechanics", json=make_mechanic_payload(), headers=headers)

    assert cached_client.get("/mechanics", headers=headers).json["total"] == 2


def test_update_mechanic_refreshes_cached_list(cached_client):
    """Updating a mechanic clears the cache, so the list shows the
    new values immediately."""
    headers = _manager_headers(cached_client)
    created = cached_client.post(
        "/mechanics", json=make_mechanic_payload(), headers=headers
    ).json
    mechanic_id = created["id"]

    listing = cached_client.get("/mechanics", headers=headers).json
    entry = next(m for m in listing["mechanics"] if m["id"] == mechanic_id)
    assert entry["salary"] == "55000.00"

    cached_client.put(
        f"/mechanics/{mechanic_id}",
        json=make_mechanic_payload(salary=60000.00),
        headers=headers,
    )

    listing = cached_client.get("/mechanics", headers=headers).json
    entry = next(m for m in listing["mechanics"] if m["id"] == mechanic_id)
    assert entry["salary"] == "60000.00"


def test_delete_mechanic_refreshes_cached_list(cached_client):
    """Deleting a mechanic clears the cache, so the deleted mechanic
    disappears from it immediately."""
    headers = _manager_headers(cached_client)
    created = cached_client.post(
        "/mechanics", json=make_mechanic_payload(), headers=headers
    ).json
    mechanic_id = created["id"]

    listing = cached_client.get("/mechanics", headers=headers).json
    assert any(m["id"] == mechanic_id for m in listing["mechanics"])

    cached_client.delete(f"/mechanics/{mechanic_id}", headers=headers)

    listing = cached_client.get("/mechanics", headers=headers).json
    assert not any(m["id"] == mechanic_id for m in listing["mechanics"])


def test_different_pages_both_invalidate_on_write(cached_client):
    """A write must invalidate every cached page, not just page 1 --
    this is the bug cache.clear() (instead of a single-key delete)
    exists to prevent."""
    headers = _manager_headers(cached_client)
    for i in range(3):
        cached_client.post(
            "/mechanics", json=make_mechanic_payload(index=i), headers=headers
        )

    # Prime BOTH pages into the cache.
    cached_client.get("/mechanics?page=1&page_size=2", headers=headers)
    cached_client.get("/mechanics?page=2&page_size=2", headers=headers)

    cached_client.post(
        "/mechanics", json=make_mechanic_payload(index=99), headers=headers
    )

    page_two = cached_client.get("/mechanics?page=2&page_size=2", headers=headers).json
    assert page_two["total"] == 5  # manager + 4 mechanics, not the stale 4
