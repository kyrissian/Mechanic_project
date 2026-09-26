"""Tests for customer login and token-protected routes."""

from app.models.service_ticket import ServiceTicket
from tests.conftest import login_customer, make_customer_payload, make_service_ticket_kwargs


def test_login_returns_token_for_valid_credentials(client):
    """POST /customers/login should return 200 and a JWT when the
    email and password match a registered customer."""
    payload = make_customer_payload()
    client.post("/customers", json=payload)

    response = client.post(
        "/customers/login",
        json={"email": payload["email"], "password": payload["password"]},
    )

    assert response.status_code == 200
    assert "auth_token" in response.json


def test_login_rejects_wrong_password(client):
    """POST /customers/login should return 401 for a registered email
    with an incorrect password."""
    payload = make_customer_payload()
    client.post("/customers", json=payload)

    response = client.post(
        "/customers/login",
        json={"email": payload["email"], "password": "wrong-password"},
    )

    assert response.status_code == 401
    assert "error" in response.json


def test_login_rejects_unknown_email(client):
    """POST /customers/login should return 401 for an email that
    isn't registered at all, with the same message as a wrong
    password -- so a client can't tell the two cases apart."""
    response = client.post(
        "/customers/login",
        json={"email": "nobody@example.com", "password": "whatever"},
    )

    assert response.status_code == 401


def test_login_rejects_missing_fields(client):
    """POST /customers/login should return a 400 when password is
    missing from the request body."""
    response = client.post(
        "/customers/login", json={"email": "jamie@example.com"}
    )

    assert response.status_code == 400


def test_password_is_never_returned_in_responses(client):
    """A customer's plaintext password and hashed password must never
    appear in any serialized response."""
    response = client.post("/customers", json=make_customer_payload())

    assert "password" not in response.json
    assert "password_hash" not in response.json


def test_my_tickets_requires_token(client):
    """GET /customers/my-tickets should return 401 with no
    Authorization header."""
    response = client.get("/customers/my-tickets")

    assert response.status_code == 401


def test_my_tickets_rejects_invalid_token(client):
    """GET /customers/my-tickets should return 401 for a syntactically
    well-formed but bogus token."""
    response = client.get(
        "/customers/my-tickets",
        headers={"Authorization": "Bearer not-a-real-token"},
    )

    assert response.status_code == 401


def test_my_tickets_rejects_malformed_authorization_header(client):
    """GET /customers/my-tickets should return 401 when the header
    doesn't follow the 'Bearer <token>' format at all."""
    response = client.get(
        "/customers/my-tickets",
        headers={"Authorization": "not-bearer-format"},
    )

    assert response.status_code == 401


def test_my_tickets_empty_list_when_no_tickets(client):
    """GET /customers/my-tickets should return an empty list for a
    logged-in customer who has no service tickets yet."""
    _, headers = login_customer(client)

    response = client.get("/customers/my-tickets", headers=headers)

    assert response.status_code == 200
    assert response.json == []


def test_my_tickets_returns_only_own_tickets(client, db):
    """GET /customers/my-tickets should return only the tickets
    belonging to the logged-in customer, never another customer's."""
    customer_id, headers = login_customer(client)
    other_id, _ = login_customer(client, name="Other", email="other@example.com")

    db.session.add(ServiceTicket(
        customer_id=customer_id,
        **make_service_ticket_kwargs(service_desc="Oil change"),
    ))
    db.session.add(ServiceTicket(
        customer_id=other_id,
        **make_service_ticket_kwargs(
            vin="2T1BURHE0JC014678", service_desc="Tire rotation"
        ),
    ))
    db.session.commit()

    response = client.get("/customers/my-tickets", headers=headers)

    assert response.status_code == 200
    assert len(response.json) == 1
    assert response.json[0]["service_desc"] == "Oil change"
