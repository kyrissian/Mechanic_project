"""Tests for the ServiceTicket routes, including mechanic assignment."""


def create_test_customer(client):
    """Helper: create a customer and return its id, since every
    service ticket needs a real customer_id to attach to."""
    response = client.post(
        "/customers",
        json={"name": "Jamie Rivera", "email": "jamie@example.com", "phone": "555-123-4567"},
    )
    return response.json["id"]


def create_test_mechanic(client, email="alex@example.com"):
    """Helper: create a mechanic and return its id."""
    response = client.post(
        "/mechanics",
        json={"name": "Alex Chen", "email": email, "phone": "555-987-6543", "salary": 55000.00},
    )
    return response.json["id"]


def make_ticket_payload(customer_id, **overrides):
    """Default JSON body for creating a service ticket."""
    payload = {
        "customer_id": customer_id,
        "vin": "1HGCM82633A004352",
        "service_date": "2026-01-05",
        "service_desc": "Brake pad replacement",
    }
    payload.update(overrides)
    return payload


def test_create_service_ticket(client):
    """POST /service-tickets should create a ticket linked to the
    given customer_id."""
    customer_id = create_test_customer(client)

    response = client.post(
        "/service-tickets", json=make_ticket_payload(customer_id)
    )

    assert response.status_code == 201
    assert response.json["customer_id"] == customer_id
    assert response.json["vin"] == "1HGCM82633A004352"


def test_create_service_ticket_rejects_missing_field(client):
    """POST /service-tickets should return a 400 when a required
    field (vin) is missing."""
    customer_id = create_test_customer(client)
    incomplete_payload = {
        "customer_id": customer_id,
        "service_date": "2026-01-05",
        "service_desc": "Brake pad replacement",
    }

    response = client.post("/service-tickets", json=incomplete_payload)

    assert response.status_code == 400
    assert "vin" in response.json


def test_create_service_ticket_rejects_invalid_customer_id(client):
    """POST /service-tickets should return a 404, not silently create
    an orphaned ticket, when customer_id doesn't refer to a real
    customer."""
    response = client.post(
        "/service-tickets", json=make_ticket_payload(customer_id=999)
    )

    assert response.status_code == 404


def test_get_service_tickets(client):
    """GET /service-tickets should return every ticket that's been created."""
    customer_id = create_test_customer(client)
    client.post("/service-tickets", json=make_ticket_payload(customer_id))
    client.post(
        "/service-tickets",
        json=make_ticket_payload(customer_id, vin="2T1BURHE0JC014678"),
    )

    response = client.get("/service-tickets")

    assert response.status_code == 200
    assert len(response.json) == 2


def test_get_single_service_ticket(client):
    """GET /service-tickets/<id> should return that specific ticket's
    data. Extra credit -- not required by the assignment, added for
    parity with Customer and Mechanic."""
    customer_id = create_test_customer(client)
    created = client.post(
        "/service-tickets", json=make_ticket_payload(customer_id)
    ).json

    response = client.get(f"/service-tickets/{created['id']}")

    assert response.status_code == 200
    assert response.json["vin"] == "1HGCM82633A004352"


def test_get_single_service_ticket_not_found(client):
    """GET /service-tickets/<id> should return a 404 for an id that
    doesn't exist."""
    response = client.get("/service-tickets/999")

    assert response.status_code == 404


def test_assign_mechanic_to_ticket(client):
    """PUT /service-tickets/<id>/assign-mechanic/<id> should add the
    mechanic to the ticket's list of assigned mechanics."""
    customer_id = create_test_customer(client)
    mechanic_id = create_test_mechanic(client)
    ticket_id = client.post(
        "/service-tickets", json=make_ticket_payload(customer_id)
    ).json["id"]

    response = client.put(
        f"/service-tickets/{ticket_id}/assign-mechanic/{mechanic_id}"
    )

    assert response.status_code == 200
    assert mechanic_id in response.json["mechanic_ids"]


def test_assign_mechanic_rejects_duplicate_assignment(client):
    """Assigning the same mechanic to the same ticket twice should be
    rejected, not silently create a duplicate link."""
    customer_id = create_test_customer(client)
    mechanic_id = create_test_mechanic(client)
    ticket_id = client.post(
        "/service-tickets", json=make_ticket_payload(customer_id)
    ).json["id"]

    client.put(f"/service-tickets/{ticket_id}/assign-mechanic/{mechanic_id}")
    response = client.put(
        f"/service-tickets/{ticket_id}/assign-mechanic/{mechanic_id}"
    )

    assert response.status_code == 400


def test_assign_mechanic_ticket_not_found(client):
    """Assigning a mechanic to a ticket id that doesn't exist should
    return a 404."""
    mechanic_id = create_test_mechanic(client)

    response = client.put(f"/service-tickets/999/assign-mechanic/{mechanic_id}")

    assert response.status_code == 404


def test_assign_mechanic_mechanic_not_found(client):
    """Assigning a mechanic id that doesn't exist should return a 404."""
    customer_id = create_test_customer(client)
    ticket_id = client.post(
        "/service-tickets", json=make_ticket_payload(customer_id)
    ).json["id"]

    response = client.put(f"/service-tickets/{ticket_id}/assign-mechanic/999")

    assert response.status_code == 404


def test_remove_mechanic_from_ticket(client):
    """PUT /service-tickets/<id>/remove-mechanic/<id> should remove a
    previously assigned mechanic."""
    customer_id = create_test_customer(client)
    mechanic_id = create_test_mechanic(client)
    ticket_id = client.post(
        "/service-tickets", json=make_ticket_payload(customer_id)
    ).json["id"]
    client.put(f"/service-tickets/{ticket_id}/assign-mechanic/{mechanic_id}")

    response = client.put(
        f"/service-tickets/{ticket_id}/remove-mechanic/{mechanic_id}"
    )

    assert response.status_code == 200
    assert mechanic_id not in response.json["mechanic_ids"]


def test_remove_mechanic_rejects_when_not_assigned(client):
    """Removing a mechanic who was never assigned to the ticket
    should be rejected, not silently succeed."""
    customer_id = create_test_customer(client)
    mechanic_id = create_test_mechanic(client)
    ticket_id = client.post(
        "/service-tickets", json=make_ticket_payload(customer_id)
    ).json["id"]

    response = client.put(
        f"/service-tickets/{ticket_id}/remove-mechanic/{mechanic_id}"
    )

    assert response.status_code == 400


def test_remove_mechanic_ticket_not_found(client):
    """Removing a mechanic from a ticket id that doesn't exist should
    return a 404."""
    mechanic_id = create_test_mechanic(client)

    response = client.put(f"/service-tickets/999/remove-mechanic/{mechanic_id}")

    assert response.status_code == 404


def test_remove_mechanic_mechanic_not_found(client):
    """Removing a mechanic id that doesn't exist should return a 404."""
    customer_id = create_test_customer(client)
    ticket_id = client.post(
        "/service-tickets", json=make_ticket_payload(customer_id)
    ).json["id"]

    response = client.put(f"/service-tickets/{ticket_id}/remove-mechanic/999")

    assert response.status_code == 404
