"""Tests for the Mechanic CRUD routes."""


def make_mechanic_payload(**overrides):
    """Default JSON body for creating/updating a mechanic in route
    tests, following the same pattern as make_customer_payload."""
    payload = {
        "name": "Alex Chen",
        "email": "alex@example.com",
        "phone": "555-987-6543",
        "salary": 55000.00,
    }
    payload.update(overrides)
    return payload


def test_create_mechanic(client):
    """POST /mechanics should create a mechanic and return it with a
    201 status and a server-assigned id."""
    response = client.post("/mechanics", json=make_mechanic_payload())

    assert response.status_code == 201
    assert response.json["name"] == "Alex Chen"
    assert response.json["salary"] == 55000.00
    assert "id" in response.json


def test_create_mechanic_rejects_duplicate_email(client):
    """POST /mechanics should reject a second mechanic using an email
    that's already registered."""
    client.post("/mechanics", json=make_mechanic_payload())
    response = client.post("/mechanics", json=make_mechanic_payload(name="Sam Diaz"))

    assert response.status_code == 400
    assert "error" in response.json


def test_create_mechanic_rejects_missing_field(client):
    """POST /mechanics should return a 400 when a required field
    (salary) is missing."""
    incomplete_payload = {
        "name": "Alex Chen",
        "email": "alex@example.com",
        "phone": "555-987-6543",
    }
    response = client.post("/mechanics", json=incomplete_payload)

    assert response.status_code == 400
    assert "salary" in response.json


def test_get_mechanics(client):
    """GET /mechanics should return every mechanic that's been created."""
    client.post("/mechanics", json=make_mechanic_payload())
    client.post(
        "/mechanics",
        json=make_mechanic_payload(name="Sam Diaz", email="sam@example.com"),
    )

    response = client.get("/mechanics")

    assert response.status_code == 200
    assert len(response.json) == 2


def test_get_single_mechanic(client):
    """GET /mechanics/<id> should return that specific mechanic's data.
    Extra credit -- not required by the assignment, added for parity
    with the Customer resource."""
    created = client.post("/mechanics", json=make_mechanic_payload()).json

    response = client.get(f"/mechanics/{created['id']}")

    assert response.status_code == 200
    assert response.json["name"] == "Alex Chen"


def test_get_single_mechanic_not_found(client):
    """GET /mechanics/<id> should return a 404 for an id that doesn't exist."""
    response = client.get("/mechanics/999")

    assert response.status_code == 404


def test_update_mechanic(client):
    """PUT /mechanics/<id> should replace the mechanic's fields with
    the new values sent in the request."""
    created = client.post("/mechanics", json=make_mechanic_payload()).json

    response = client.put(
        f"/mechanics/{created['id']}",
        json=make_mechanic_payload(salary=60000.00),
    )

    assert response.status_code == 200
    assert response.json["salary"] == 60000.00


def test_update_mechanic_rejects_duplicate_email(client):
    """PUT /mechanics/<id> should reject changing a mechanic's email
    to one already used by a different mechanic."""
    client.post("/mechanics", json=make_mechanic_payload())
    other = client.post(
        "/mechanics", json=make_mechanic_payload(name="Sam Diaz", email="sam@example.com")
    ).json

    response = client.put(
        f"/mechanics/{other['id']}",
        json=make_mechanic_payload(name="Sam Diaz"),
    )

    assert response.status_code == 400
    assert "error" in response.json


def test_update_mechanic_not_found(client):
    """PUT /mechanics/<id> should return a 404 for an id that doesn't exist."""
    response = client.put("/mechanics/999", json=make_mechanic_payload())

    assert response.status_code == 404


def test_delete_mechanic(client):
    """DELETE /mechanics/<id> should remove the mechanic, and a
    follow-up GET should no longer list it."""
    created = client.post("/mechanics", json=make_mechanic_payload()).json

    response = client.delete(f"/mechanics/{created['id']}")
    assert response.status_code == 200

    remaining = client.get("/mechanics").json
    assert remaining == []


def test_delete_mechanic_not_found(client):
    """DELETE /mechanics/<id> should return a 404 for an id that doesn't exist."""
    response = client.delete("/mechanics/999")

    assert response.status_code == 404
