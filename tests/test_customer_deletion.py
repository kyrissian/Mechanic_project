"""Tests for closing a customer account: only customers without service
history may do it, and it is a soft delete with anonymization."""

from datetime import datetime

from app.models.customer import Customer
from tests.conftest import (
    create_ticket,
    login_customer,
    make_customer_kwargs,
    make_customer_payload,
)


def test_delete_customer_anonymizes_account(client, db):
    """DELETE /customers/<id> keeps the row but scrubs everything that
    identifies the person."""
    customer_id, headers = login_customer(client)

    response = client.delete(f"/customers/{customer_id}", headers=headers)

    assert response.status_code == 200
    saved = db.session.get(Customer, customer_id)
    assert saved is not None
    assert saved.is_active is False
    assert saved.name == "Deleted Customer"
    assert saved.email == f"deleted-{customer_id}@deleted.invalid"
    assert saved.phone == "N/A"


def test_customer_with_tickets_cannot_delete_account(client, manager):
    """A customer who has had work done can't close their account; the
    account, the login, and the ticket are all left alone."""
    _, manager_headers = manager
    customer_id, headers = login_customer(client)
    ticket_id = create_ticket(client, manager_headers, customer_id=customer_id)

    response = client.delete(f"/customers/{customer_id}", headers=headers)

    assert response.status_code == 409
    assert client.get(f"/customers/{customer_id}", headers=manager_headers).status_code == 200
    my_tickets = client.get("/customers/my-tickets", headers=headers)
    assert my_tickets.status_code == 200
    assert my_tickets.json["tickets"][0]["id"] == ticket_id


def test_customer_with_finished_ticket_still_cannot_delete(client, manager):
    """The rule covers a ticket in ANY status, including one that is
    fully done (Picked Up), not just open work."""
    _, manager_headers = manager
    customer_id, headers = login_customer(client)
    ticket_id = create_ticket(client, manager_headers, customer_id=customer_id)
    client.put(
        f"/service-tickets/{ticket_id}/status",
        json={"status": "Picked Up"},
        headers=manager_headers,
    )

    response = client.delete(f"/customers/{customer_id}", headers=headers)

    assert response.status_code == 409


def test_deleted_customer_cannot_log_in(client):
    """The original credentials no longer work after the account is closed."""
    payload = make_customer_payload()
    customer_id, headers = login_customer(client)
    client.delete(f"/customers/{customer_id}", headers=headers)

    response = client.post(
        "/customers/login",
        json={"email": payload["email"], "password": payload["password"]},
    )

    assert response.status_code == 401


def test_deleted_customer_token_stops_working(client):
    """A token issued before the account was closed is rejected
    everywhere afterward, instead of working until it expires."""
    customer_id, headers = login_customer(client)
    client.delete(f"/customers/{customer_id}", headers=headers)

    my_tickets = client.get("/customers/my-tickets", headers=headers)
    update = client.put(
        f"/customers/{customer_id}", json=make_customer_payload(), headers=headers
    )
    second_delete = client.delete(f"/customers/{customer_id}", headers=headers)

    assert my_tickets.status_code == 401
    assert update.status_code == 401
    assert second_delete.status_code == 401


def test_deleted_customer_hidden_from_list_and_lookup(client, mechanic):
    """A closed account disappears from the list (and its total) and
    from the single-customer lookup."""
    _, mechanic_headers = mechanic
    closed_id, closed_headers = login_customer(client)
    login_customer(client, name="Other", email="other@example.com")
    client.delete(f"/customers/{closed_id}", headers=closed_headers)

    listing = client.get("/customers", headers=mechanic_headers)
    lookup = client.get(f"/customers/{closed_id}", headers=mechanic_headers)

    assert listing.json["total"] == 1
    assert listing.json["customers"][0]["email"] == "other@example.com"
    assert lookup.status_code == 404


def test_email_can_be_reused_after_account_closed(client):
    """Closing an account frees the original email for a new sign-up."""
    customer_id, headers = login_customer(client)
    client.delete(f"/customers/{customer_id}", headers=headers)

    response = client.post("/customers", json=make_customer_payload())

    assert response.status_code == 201


def test_cannot_create_ticket_for_deleted_customer(client, manager):
    """A manager can't open a new ticket under a closed account."""
    _, manager_headers = manager
    customer_id, headers = login_customer(client)
    client.delete(f"/customers/{customer_id}", headers=headers)

    response = client.post(
        "/service-tickets",
        json={
            "customer_id": customer_id,
            "vin": "JH4KA8270MC000001",
            "service_date": "2026-03-01",
            "service_desc": "Tire rotation",
            "cost": "60.00",
        },
        headers=manager_headers,
    )

    assert response.status_code == 404


def test_deleted_at_cannot_be_set_through_the_api(client):
    """A client can't close (or reopen) an account by sending
    deleted_at on create or update; only the delete route sets it."""
    response = client.post(
        "/customers", json=make_customer_payload(deleted_at="2026-01-01T00:00:00")
    )

    assert response.status_code == 400
    assert "deleted_at" in response.json["details"]


def test_customer_is_active_until_deleted_at_is_set(db):
    """is_active is True for a new customer and False once deleted_at is set."""
    customer = Customer(**make_customer_kwargs())
    db.session.add(customer)
    db.session.commit()
    assert customer.is_active is True

    customer.deleted_at = datetime(2026, 1, 1)
    db.session.commit()

    assert customer.is_active is False
