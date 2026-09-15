"""Tests for the Customer CRUD routes."""

from app.models.customer import Customer


def make_customer_payload(**overrides):
    """Default JSON body for creating/updating a customer in route
    tests. Same idea as make_service_ticket_kwargs in conftest.py --
    a shared default, with only the fields a test cares about
    overridden."""
    payload = {
        "name": "Jamie Rivera",
        "email": "jamie@example.com",
        "phone": "555-123-4567",
    }
    payload.update(overrides)
    return payload


def test_create_customer(client):
    """POST /customers should create a customer and return it with a
    201 status and a server-assigned id."""
    response = client.post("/customers", json=make_customer_payload())

    assert response.status_code == 201
    assert response.json["name"] == "Jamie Rivera"
    assert response.json["email"] == "jamie@example.com"
    assert "id" in response.json


def test_create_customer_rejects_duplicate_email(client):
    """POST /customers should reject a second customer using an email
    that's already registered."""
    client.post("/customers", json=make_customer_payload())
    response = client.post(
        "/customers", json=make_customer_payload(name="Someone Else")
    )

    assert response.status_code == 400
    assert "error" in response.json


def test_create_customer_rejects_missing_field(client):
    """POST /customers should return a 400 with validation details
    when a required field (email) is missing, rather than a server
    error or a silently invalid record."""
    incomplete_payload = {"name": "Jamie Rivera", "phone": "555-123-4567"}
    response = client.post("/customers", json=incomplete_payload)

    assert response.status_code == 400
    assert "email" in response.json


def test_get_customers(client):
    """GET /customers should return every customer that's been created."""
    client.post("/customers", json=make_customer_payload())
    client.post(
        "/customers",
        json=make_customer_payload(name="Sam Diaz", email="sam@example.com"),
    )

    response = client.get("/customers")

    assert response.status_code == 200
    assert len(response.json) == 2


def test_get_single_customer(client):
    """GET /customers/<id> should return that specific customer's data."""
    created = client.post("/customers", json=make_customer_payload()).json

    response = client.get(f"/customers/{created['id']}")

    assert response.status_code == 200
    assert response.json["name"] == "Jamie Rivera"


def test_get_single_customer_not_found(client):
    """GET /customers/<id> should return a 404 for an id that doesn't exist."""
    response = client.get("/customers/999")

    assert response.status_code == 404


def test_update_customer(client):
    """PUT /customers/<id> should replace the customer's fields with
    the new values sent in the request."""
    created = client.post("/customers", json=make_customer_payload()).json

    response = client.put(
        f"/customers/{created['id']}",
        json=make_customer_payload(name="Jamie R. Updated"),
    )

    assert response.status_code == 200
    assert response.json["name"] == "Jamie R. Updated"


def test_update_customer_not_found(client):
    """PUT /customers/<id> should return a 404 for an id that doesn't exist."""
    response = client.put("/customers/999", json=make_customer_payload())

    assert response.status_code == 404


def test_delete_customer(client, db):
    """DELETE /customers/<id> should remove the customer, and it
    should no longer exist in the database afterward."""
    created = client.post("/customers", json=make_customer_payload()).json

    response = client.delete(f"/customers/{created['id']}")

    assert response.status_code == 200
    assert db.session.get(Customer, created["id"]) is None


def test_delete_customer_not_found(client):
    """DELETE /customers/<id> should return a 404 for an id that doesn't exist."""
    response = client.delete("/customers/999")

    assert response.status_code == 404
