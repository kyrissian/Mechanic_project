"""Tests for the Customer CRUD routes."""

from app.models.customer import Customer
from tests.conftest import login_customer, make_customer_payload


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
    incomplete_payload = {
        "name": "Jamie Rivera",
        "phone": "555-123-4567",
        "password": "hunter2",
    }
    response = client.post("/customers", json=incomplete_payload)

    assert response.status_code == 400
    assert "email" in response.json["details"]


def test_create_customer_rejects_missing_password(client):
    """POST /customers should return a 400 when password is missing --
    it's required now that customer accounts support login."""
    incomplete_payload = {
        "name": "Jamie Rivera",
        "email": "jamie@example.com",
        "phone": "555-123-4567",
    }
    response = client.post("/customers", json=incomplete_payload)

    assert response.status_code == 400
    assert "password" in response.json["details"]


def test_get_customers_default_pagination(client):
    """GET /customers with no query params should return the first
    page, 7 per page, wrapped in the pagination envelope."""
    for i in range(9):
        client.post("/customers", json=make_customer_payload(i))

    response = client.get("/customers")

    assert response.status_code == 200
    assert len(response.json["customers"]) == 7
    assert response.json["total"] == 9
    assert response.json["page"] == 1
    assert response.json["page_size"] == 7
    assert response.json["total_pages"] == 2


def test_get_customers_second_page(client):
    """?page=2 should return the remaining customers past the first
    page_size worth."""
    for i in range(9):
        client.post("/customers", json=make_customer_payload(i))

    response = client.get("/customers?page=2")

    assert response.status_code == 200
    assert len(response.json["customers"]) == 2
    assert response.json["page"] == 2


def test_get_customers_custom_page_size(client):
    """?page_size should override the default of 7."""
    for i in range(5):
        client.post("/customers", json=make_customer_payload(i))

    response = client.get("/customers?page_size=3")

    assert response.status_code == 200
    assert len(response.json["customers"]) == 3
    assert response.json["page_size"] == 3
    assert response.json["total_pages"] == 2


def test_get_customers_page_size_is_capped(client):
    """A page_size above the cap (50) should be clamped down rather
    than returning an unbounded number of rows."""
    for i in range(3):
        client.post("/customers", json=make_customer_payload(i))

    response = client.get("/customers?page_size=9999")

    assert response.status_code == 200
    assert response.json["page_size"] == 50
    assert len(response.json["customers"]) == 3


def test_get_customers_page_past_the_end(client):
    """Requesting a page beyond the last real page should return an
    empty list, not a 404 -- the request itself is valid, there's
    just no data there."""
    client.post("/customers", json=make_customer_payload())

    response = client.get("/customers?page=999")

    assert response.status_code == 200
    assert response.json["customers"] == []
    assert response.json["total"] == 1


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
    the new values sent in the request, when authenticated as the
    customer being updated."""
    customer_id, headers = login_customer(client)

    response = client.put(
        f"/customers/{customer_id}",
        json=make_customer_payload(name="Jamie R. Updated"),
        headers=headers,
    )

    assert response.status_code == 200
    assert response.json["name"] == "Jamie R. Updated"


def test_update_customer_requires_token(client):
    """PUT /customers/<id> should return 401 with no Authorization header."""
    created = client.post("/customers", json=make_customer_payload()).json

    response = client.put(
        f"/customers/{created['id']}",
        json=make_customer_payload(name="Someone Else"),
    )

    assert response.status_code == 401


def test_update_customer_rejects_wrong_customer(client):
    """A logged-in customer may not update a different customer's
    account, even with a valid token of their own."""
    login_customer(client)
    other_id, _ = login_customer(client, name="Other", email="other@example.com")
    _, headers = login_customer(client, name="Third", email="third@example.com")

    response = client.put(
        f"/customers/{other_id}",
        json=make_customer_payload(name="Hacked"),
        headers=headers,
    )

    assert response.status_code == 403


def test_update_customer_rejects_duplicate_email(client):
    """PUT /customers/<id> should reject changing a customer's email
    to one already used by a different customer."""
    client.post("/customers", json=make_customer_payload())
    other_id, other_headers = login_customer(
        client, name="Sam Diaz", email="sam@example.com"
    )

    response = client.put(
        f"/customers/{other_id}",
        json=make_customer_payload(name="Sam Diaz", email="jamie@example.com"),
        headers=other_headers,
    )

    assert response.status_code == 400
    assert "error" in response.json


def test_update_customer_allows_keeping_own_email(client):
    """PUT /customers/<id> should not reject a customer keeping their
    own existing email while changing another field -- the duplicate
    check must exclude the customer's own row."""
    customer_id, headers = login_customer(client)

    response = client.put(
        f"/customers/{customer_id}",
        json=make_customer_payload(name="Jamie R. Updated"),
        headers=headers,
    )

    assert response.status_code == 200


def test_update_customer_not_found(client):
    """PUT /customers/<id> should return a 404 when the authenticated
    customer's own record no longer exists -- e.g. it was deleted
    earlier in the same still-valid session."""
    customer_id, headers = login_customer(client)
    client.delete(f"/customers/{customer_id}", headers=headers)

    response = client.put(
        f"/customers/{customer_id}",
        json=make_customer_payload(),
        headers=headers,
    )

    assert response.status_code == 404


def test_delete_customer(client, db):
    """DELETE /customers/<id> should remove the customer, and it
    should no longer exist in the database afterward."""
    customer_id, headers = login_customer(client)

    response = client.delete(f"/customers/{customer_id}", headers=headers)

    assert response.status_code == 200
    assert db.session.get(Customer, customer_id) is None


def test_delete_customer_requires_token(client):
    """DELETE /customers/<id> should return 401 with no Authorization header."""
    response = client.delete("/customers/999")

    assert response.status_code == 401


def test_delete_customer_rejects_wrong_customer(client, db):
    """A logged-in customer may not delete a different customer's
    account, even with a valid token of their own."""
    other_id, _ = login_customer(client, name="Other", email="other@example.com")
    _, headers = login_customer(client, name="Third", email="third@example.com")

    response = client.delete(f"/customers/{other_id}", headers=headers)

    assert response.status_code == 403
    assert db.session.get(Customer, other_id) is not None


def test_delete_customer_not_found(client):
    """DELETE /customers/<id> should return a 404 when called again
    after the customer's own account was already deleted -- the token
    is still valid, but the record is gone."""
    customer_id, headers = login_customer(client)
    client.delete(f"/customers/{customer_id}", headers=headers)

    response = client.delete(f"/customers/{customer_id}", headers=headers)

    assert response.status_code == 404
