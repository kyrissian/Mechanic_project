"""Tests for the Mechanic CRUD routes and the role-based access
rules around them."""

from tests.conftest import create_mechanic, make_mechanic_payload


def test_create_mechanic_requires_manager(client, manager):
    """POST /mechanics should succeed when authenticated as a manager."""
    _, manager_headers = manager

    response = client.post(
        "/mechanics", json=make_mechanic_payload(), headers=manager_headers
    )

    assert response.status_code == 201
    assert response.json["name"] == "Alex Chen"
    assert response.json["role"] == "mechanic"
    assert "id" in response.json


def test_create_mechanic_rejects_regular_mechanic(client, mechanic):
    """A regular mechanic may not create a mechanic account, even
    with a valid token of their own."""
    _, mechanic_headers = mechanic

    response = client.post(
        "/mechanics", json=make_mechanic_payload(index=2), headers=mechanic_headers
    )

    assert response.status_code == 403


def test_create_mechanic_requires_token(client):
    """POST /mechanics should return 401 with no Authorization header."""
    response = client.post("/mechanics", json=make_mechanic_payload())

    assert response.status_code == 401


def test_create_mechanic_rejects_duplicate_email(client, manager):
    """POST /mechanics should reject a second mechanic using an email
    that's already registered."""
    _, manager_headers = manager
    client.post("/mechanics", json=make_mechanic_payload(), headers=manager_headers)

    response = client.post(
        "/mechanics",
        json=make_mechanic_payload(name="Sam Diaz"),
        headers=manager_headers,
    )

    assert response.status_code == 400
    assert "error" in response.json


def test_create_mechanic_rejects_missing_field(client, manager):
    """POST /mechanics should return a 400 when a required field
    (salary) is missing."""
    _, manager_headers = manager
    incomplete_payload = {
        "name": "Alex Chen",
        "email": "alex@example.com",
        "phone": "555-987-6543",
        "password": "wrench123",
        "role": "mechanic",
    }

    response = client.post(
        "/mechanics", json=incomplete_payload, headers=manager_headers
    )

    assert response.status_code == 400
    assert "salary" in response.json["details"]


def test_create_mechanic_rejects_invalid_role(client, manager):
    """POST /mechanics should reject a role outside "mechanic"/"manager"."""
    _, manager_headers = manager

    response = client.post(
        "/mechanics", json=make_mechanic_payload(role="owner"), headers=manager_headers
    )

    assert response.status_code == 400
    assert "role" in response.json["details"]


def test_get_mechanics_requires_manager(client, manager, mechanic):
    """GET /mechanics (the full roster, including salary) should
    succeed for a manager. Depends on the mechanic fixture existing
    so the roster has two entries to count."""
    _, manager_headers = manager
    _mechanic_id, _ = mechanic  # unpacked to confirm the fixture ran; unused otherwise

    response = client.get("/mechanics", headers=manager_headers)

    assert response.status_code == 200
    assert len(response.json) == 2  # the manager and the mechanic fixture
    assert "salary" in response.json[0]


def test_get_mechanics_rejects_regular_mechanic(client, mechanic):
    """A regular mechanic may not see the full roster -- it exposes
    every mechanic's salary."""
    _, mechanic_headers = mechanic

    response = client.get("/mechanics", headers=mechanic_headers)

    assert response.status_code == 403


def test_get_own_profile(client, mechanic):
    """GET /mechanics/<own_id> should succeed for a regular mechanic
    looking up their own profile, including their own salary."""
    mechanic_id, mechanic_headers = mechanic

    response = client.get(f"/mechanics/{mechanic_id}", headers=mechanic_headers)

    assert response.status_code == 200
    assert response.json["name"] == "Alex Chen"
    assert "salary" in response.json


def test_get_other_mechanic_profile_rejected(client, manager, mechanic):
    """A regular mechanic may NOT look up a different mechanic's
    profile -- exactly the salary-visibility protection this role
    system exists to provide."""
    _, manager_headers = manager
    other_id, _ = create_mechanic(client, manager_headers, index=2)
    _, mechanic_headers = mechanic

    response = client.get(f"/mechanics/{other_id}", headers=mechanic_headers)

    assert response.status_code == 403


def test_manager_can_view_any_mechanic_profile(client, manager, mechanic):
    """A manager may look up any mechanic's profile, not just their own."""
    mechanic_id, _ = mechanic
    _, manager_headers = manager

    response = client.get(f"/mechanics/{mechanic_id}", headers=manager_headers)

    assert response.status_code == 200


def test_get_mechanic_not_found(client, manager):
    """GET /mechanics/<id> should return a 404 for an id that doesn't exist."""
    _, manager_headers = manager

    response = client.get("/mechanics/999", headers=manager_headers)

    assert response.status_code == 404


def test_update_mechanic_requires_manager(client, manager, mechanic):
    """PUT /mechanics/<id> should succeed when authenticated as a manager."""
    mechanic_id, _ = mechanic
    _, manager_headers = manager

    response = client.put(
        f"/mechanics/{mechanic_id}",
        json=make_mechanic_payload(salary=60000.00),
        headers=manager_headers,
    )

    assert response.status_code == 200
    assert response.json["salary"] == "60000.00"


def test_update_mechanic_rejects_regular_mechanic(client, mechanic):
    """A regular mechanic may not update any mechanic's record,
    including their own -- roster changes are manager-only."""
    mechanic_id, mechanic_headers = mechanic

    response = client.put(
        f"/mechanics/{mechanic_id}",
        json=make_mechanic_payload(salary=99999.00),
        headers=mechanic_headers,
    )

    assert response.status_code == 403


def test_update_mechanic_rejects_duplicate_email(client, manager, mechanic):
    """PUT /mechanics/<id> should reject changing a mechanic's email
    to one already used by a different mechanic."""
    _, manager_headers = manager
    mechanic_id, _ = mechanic
    create_mechanic(client, manager_headers, index=2, email="sam@example.com")

    response = client.put(
        f"/mechanics/{mechanic_id}",
        json=make_mechanic_payload(email="sam@example.com"),
        headers=manager_headers,
    )

    assert response.status_code == 400
    assert "error" in response.json


def test_update_mechanic_not_found(client, manager):
    """PUT /mechanics/<id> should return a 404 for an id that doesn't exist."""
    _, manager_headers = manager

    response = client.put(
        "/mechanics/999", json=make_mechanic_payload(), headers=manager_headers
    )

    assert response.status_code == 404


def test_delete_mechanic_requires_manager(client, manager, mechanic):
    """DELETE /mechanics/<id> should succeed when authenticated as a manager."""
    mechanic_id, _ = mechanic
    _, manager_headers = manager

    response = client.delete(f"/mechanics/{mechanic_id}", headers=manager_headers)

    assert response.status_code == 200


def test_delete_mechanic_rejects_regular_mechanic(client, mechanic):
    """A regular mechanic may not delete any mechanic account,
    including their own."""
    mechanic_id, mechanic_headers = mechanic

    response = client.delete(f"/mechanics/{mechanic_id}", headers=mechanic_headers)

    assert response.status_code == 403


def test_delete_mechanic_not_found(client, manager):
    """DELETE /mechanics/<id> should return a 404 for an id that
    doesn't exist."""
    _, manager_headers = manager

    response = client.delete("/mechanics/999", headers=manager_headers)

    assert response.status_code == 404
