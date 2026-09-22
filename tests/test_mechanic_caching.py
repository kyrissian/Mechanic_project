"""Tests for caching on GET /mechanics and its invalidation on writes."""

from app.extensions import db as _db
from app.models.mechanic import Mechanic
from tests.conftest import make_mechanic_payload


def insert_mechanic_directly():
    """Insert a mechanic straight into the database, bypassing the API.

    Because the routes never see this write, they can't clear the
    cache, which makes it a clean way to tell a cached response apart
    from a fresh database query.
    """
    _db.session.add(Mechanic(**make_mechanic_payload()))
    _db.session.commit()


def test_get_mechanics_is_served_from_cache(cached_client):
    """Once the list is cached, a change the API never saw doesn't
    appear in GET /mechanics until the cache is cleared or expires."""
    assert cached_client.get("/mechanics").json == []

    insert_mechanic_directly()

    assert cached_client.get("/mechanics").json == []


def test_get_mechanics_is_not_cached_when_caching_disabled(client):
    """Control for the test above: with the default (NullCache) test
    config, the same direct insert IS visible on the next request."""
    assert client.get("/mechanics").json == []

    insert_mechanic_directly()

    assert len(client.get("/mechanics").json) == 1


def test_create_mechanic_refreshes_cached_list(cached_client):
    """Creating a mechanic clears the cached list, so the new mechanic
    shows up immediately rather than after the timeout."""
    assert cached_client.get("/mechanics").json == []

    cached_client.post("/mechanics", json=make_mechanic_payload())

    assert len(cached_client.get("/mechanics").json) == 1


def test_update_mechanic_refreshes_cached_list(cached_client):
    """Updating a mechanic clears the cached list, so the list shows
    the new values immediately."""
    created = cached_client.post("/mechanics", json=make_mechanic_payload()).json
    assert cached_client.get("/mechanics").json[0]["salary"] == 55000.00

    cached_client.put(
        f"/mechanics/{created['id']}",
        json=make_mechanic_payload(salary=60000.00),
    )

    assert cached_client.get("/mechanics").json[0]["salary"] == 60000.00


def test_delete_mechanic_refreshes_cached_list(cached_client):
    """Deleting a mechanic clears the cached list, so the deleted
    mechanic disappears from it immediately."""
    created = cached_client.post("/mechanics", json=make_mechanic_payload()).json
    assert len(cached_client.get("/mechanics").json) == 1

    cached_client.delete(f"/mechanics/{created['id']}")

    assert cached_client.get("/mechanics").json == []


def test_get_single_mechanic_is_served_from_cache(cached_client):
    """Once a single mechanic's data is cached, a change the API never
    saw doesn't appear in GET /mechanics/<id> until the cache clears."""
    created = cached_client.post("/mechanics", json=make_mechanic_payload()).json
    mechanic_id = created["id"]
    cached_client.get(f"/mechanics/{mechanic_id}")  # prime the cache

    mechanic = _db.session.get(Mechanic, mechanic_id)
    mechanic.salary = 99999.00
    _db.session.commit()  # bypasses the API, so nothing invalidates the cache

    response = cached_client.get(f"/mechanics/{mechanic_id}")
    assert response.json["salary"] == 55000.00


def test_update_mechanic_refreshes_cached_single_mechanic(cached_client):
    """Updating a mechanic clears its own cached entry, not just the
    list, so a follow-up single lookup shows the new values immediately."""
    created = cached_client.post("/mechanics", json=make_mechanic_payload()).json
    mechanic_id = created["id"]
    cached_client.get(f"/mechanics/{mechanic_id}")  # prime the cache

    cached_client.put(
        f"/mechanics/{mechanic_id}",
        json=make_mechanic_payload(salary=60000.00),
    )

    response = cached_client.get(f"/mechanics/{mechanic_id}")
    assert response.json["salary"] == 60000.00


def test_delete_mechanic_refreshes_cached_single_mechanic(cached_client):
    """Deleting a mechanic clears its cached entry, so a follow-up
    single lookup correctly returns 404 instead of stale cached data."""
    created = cached_client.post("/mechanics", json=make_mechanic_payload()).json
    mechanic_id = created["id"]
    cached_client.get(f"/mechanics/{mechanic_id}")  # prime the cache

    cached_client.delete(f"/mechanics/{mechanic_id}")

    response = cached_client.get(f"/mechanics/{mechanic_id}")
    assert response.status_code == 404
