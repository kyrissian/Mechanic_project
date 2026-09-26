"""Tests for the ServiceTicket routes: creation, reads, manager-only
description/cost edits, status updates open to any mechanic, and
both the single-action and bulk mechanic assignment routes."""

from tests.conftest import create_mechanic, make_customer_payload


def create_test_customer(client):
    """Helper: create a customer and return its id, since every
    service ticket needs a real customer_id to attach to."""
    response = client.post("/customers", json=make_customer_payload())
    return response.json["id"]


def make_ticket_payload(customer_id, **overrides):
    """Default JSON body for creating a service ticket via the API."""
    payload = {
        "customer_id": customer_id,
        "vin": "1HGCM82633A004352",
        "service_date": "2026-01-05",
        "service_desc": "Brake pad replacement",
        "cost": "450.00",
    }
    payload.update(overrides)
    return payload


def test_create_service_ticket_requires_manager(client, manager):
    """POST /service-tickets should succeed when authenticated as a manager."""
    customer_id = create_test_customer(client)
    _, manager_headers = manager

    response = client.post(
        "/service-tickets", json=make_ticket_payload(customer_id), headers=manager_headers
    )

    assert response.status_code == 201
    assert response.json["customer_id"] == customer_id
    assert response.json["vin"] == "1HGCM82633A004352"
    assert response.json["cost"] == "450.00"
    assert response.json["status"] == "Pending"


def test_create_service_ticket_rejects_regular_mechanic(client, mechanic):
    """A regular mechanic (not a manager) may not create a ticket."""
    customer_id = create_test_customer(client)
    _, mechanic_headers = mechanic

    response = client.post(
        "/service-tickets", json=make_ticket_payload(customer_id), headers=mechanic_headers
    )

    assert response.status_code == 403


def test_create_service_ticket_requires_token(client):
    """POST /service-tickets should return 401 with no Authorization header."""
    customer_id = create_test_customer(client)

    response = client.post("/service-tickets", json=make_ticket_payload(customer_id))

    assert response.status_code == 401


def test_create_service_ticket_rejects_missing_field(client, manager):
    """POST /service-tickets should return a 400 when a required
    field (vin) is missing."""
    customer_id = create_test_customer(client)
    _, manager_headers = manager
    incomplete_payload = {
        "customer_id": customer_id,
        "service_date": "2026-01-05",
        "service_desc": "Brake pad replacement",
        "cost": "450.00",
    }

    response = client.post(
        "/service-tickets", json=incomplete_payload, headers=manager_headers
    )

    assert response.status_code == 400
    assert "vin" in response.json["details"]


def test_create_service_ticket_rejects_invalid_customer_id(client, manager):
    """POST /service-tickets should return a 404, not silently create
    an orphaned ticket, when customer_id doesn't refer to a real
    customer."""
    _, manager_headers = manager

    response = client.post(
        "/service-tickets",
        json=make_ticket_payload(customer_id=999),
        headers=manager_headers,
    )

    assert response.status_code == 404


def test_create_service_ticket_rejects_short_vin(client, manager):
    """POST /service-tickets should reject a VIN shorter than the
    real-world 17-character standard, not silently accept it."""
    customer_id = create_test_customer(client)
    _, manager_headers = manager

    response = client.post(
        "/service-tickets",
        json=make_ticket_payload(customer_id, vin="ABC123"),
        headers=manager_headers,
    )

    assert response.status_code == 400
    assert "vin" in response.json["details"]


def test_create_service_ticket_rejects_long_vin(client, manager):
    """POST /service-tickets should reject a VIN longer than 17
    characters."""
    customer_id = create_test_customer(client)
    _, manager_headers = manager

    response = client.post(
        "/service-tickets",
        json=make_ticket_payload(customer_id, vin="ABCDEFGHIJKLMNOPQR"),
        headers=manager_headers,
    )

    assert response.status_code == 400
    assert "vin" in response.json["details"]


def test_create_service_ticket_rejects_lowercase_vin(client, manager):
    """POST /service-tickets should reject a VIN containing lowercase
    letters -- real VINs are always uppercase."""
    customer_id = create_test_customer(client)
    _, manager_headers = manager

    response = client.post(
        "/service-tickets",
        json=make_ticket_payload(customer_id, vin="1hgcm82633a004352"),
        headers=manager_headers,
    )

    assert response.status_code == 400
    assert "vin" in response.json["details"]


def test_create_service_ticket_rejects_excluded_letters(client, manager):
    """POST /service-tickets should reject a VIN containing I, O, or
    Q -- these letters are excluded from real VINs per ISO 3779."""
    customer_id = create_test_customer(client)
    _, manager_headers = manager

    for excluded_letter in ("I", "O", "Q"):
        vin = "1HGCM8263" + excluded_letter + "A00435" + "2"
        response = client.post(
            "/service-tickets",
            json=make_ticket_payload(customer_id, vin=vin),
            headers=manager_headers,
        )

        assert response.status_code == 400
        assert "vin" in response.json["details"]


def test_get_service_tickets(client, manager, mechanic):
    """GET /service-tickets should return every ticket that's been
    created, when authenticated as any mechanic."""
    customer_id = create_test_customer(client)
    _, manager_headers = manager
    _, mechanic_headers = mechanic

    client.post(
        "/service-tickets", json=make_ticket_payload(customer_id), headers=manager_headers
    )
    client.post(
        "/service-tickets",
        json=make_ticket_payload(customer_id, vin="2T1BURHE0JC014678"),
        headers=manager_headers,
    )

    response = client.get("/service-tickets", headers=mechanic_headers)

    assert response.status_code == 200
    assert len(response.json) == 2


def test_get_service_tickets_requires_token(client):
    """GET /service-tickets should return 401 with no Authorization header."""
    response = client.get("/service-tickets")

    assert response.status_code == 401


def test_get_single_service_ticket(client, manager, mechanic):
    """GET /service-tickets/<id> should return that specific ticket's
    data. Extra credit -- not required by the assignment."""
    customer_id = create_test_customer(client)
    _, manager_headers = manager
    _, mechanic_headers = mechanic
    created = client.post(
        "/service-tickets", json=make_ticket_payload(customer_id), headers=manager_headers
    ).json

    response = client.get(f"/service-tickets/{created['id']}", headers=mechanic_headers)

    assert response.status_code == 200
    assert response.json["vin"] == "1HGCM82633A004352"


def test_get_single_service_ticket_not_found(client, mechanic):
    """GET /service-tickets/<id> should return a 404 for an id that
    doesn't exist."""
    _, mechanic_headers = mechanic

    response = client.get("/service-tickets/999", headers=mechanic_headers)

    assert response.status_code == 404


def test_my_tickets_returns_only_assigned_tickets(client, manager, mechanic):
    """GET /service-tickets/my-tickets should return only the tickets
    the logged-in mechanic is personally assigned to."""
    customer_id = create_test_customer(client)
    _, manager_headers = manager
    mechanic_id, mechanic_headers = mechanic
    other_id, _ = create_mechanic(client, manager_headers, index=2)

    mine = client.post(
        "/service-tickets", json=make_ticket_payload(customer_id), headers=manager_headers
    ).json
    not_mine = client.post(
        "/service-tickets",
        json=make_ticket_payload(customer_id, vin="2T1BURHE0JC014678"),
        headers=manager_headers,
    ).json

    client.put(
        f"/service-tickets/{mine['id']}/assign-mechanic/{mechanic_id}",
        headers=manager_headers,
    )
    client.put(
        f"/service-tickets/{not_mine['id']}/assign-mechanic/{other_id}",
        headers=manager_headers,
    )

    response = client.get("/service-tickets/my-tickets", headers=mechanic_headers)

    assert response.status_code == 200
    assert len(response.json) == 1
    assert response.json[0]["id"] == mine["id"]


def test_my_tickets_requires_token(client):
    """GET /service-tickets/my-tickets should return 401 with no
    Authorization header."""
    response = client.get("/service-tickets/my-tickets")

    assert response.status_code == 401


def test_update_ticket_details_requires_manager(client, manager):
    """PUT /service-tickets/<id> should succeed for a manager,
    updating description and/or cost."""
    customer_id = create_test_customer(client)
    _, manager_headers = manager
    created = client.post(
        "/service-tickets", json=make_ticket_payload(customer_id), headers=manager_headers
    ).json

    response = client.put(
        f"/service-tickets/{created['id']}",
        json={"cost": "500.00"},
        headers=manager_headers,
    )

    assert response.status_code == 200
    assert response.json["cost"] == "500.00"


def test_update_ticket_details_rejects_regular_mechanic(client, manager, mechanic):
    """A regular mechanic may not edit a ticket's description or cost."""
    customer_id = create_test_customer(client)
    _, manager_headers = manager
    _, mechanic_headers = mechanic
    created = client.post(
        "/service-tickets", json=make_ticket_payload(customer_id), headers=manager_headers
    ).json

    response = client.put(
        f"/service-tickets/{created['id']}",
        json={"cost": "500.00"},
        headers=mechanic_headers,
    )

    assert response.status_code == 403


def test_update_ticket_details_rejects_empty_body(client, manager):
    """PUT /service-tickets/<id> should reject a request with neither
    service_desc nor cost, rather than silently succeeding."""
    customer_id = create_test_customer(client)
    _, manager_headers = manager
    created = client.post(
        "/service-tickets", json=make_ticket_payload(customer_id), headers=manager_headers
    ).json

    response = client.put(
        f"/service-tickets/{created['id']}", json={}, headers=manager_headers
    )

    assert response.status_code == 400


def test_update_ticket_details_not_found(client, manager):
    """PUT /service-tickets/<id> should return a 404 for an id that
    doesn't exist."""
    _, manager_headers = manager

    response = client.put(
        "/service-tickets/999", json={"cost": "500.00"}, headers=manager_headers
    )

    assert response.status_code == 404


def test_update_ticket_status_any_mechanic(client, manager, mechanic):
    """PUT /service-tickets/<id>/status should succeed for any
    logged-in mechanic, not just a manager."""
    customer_id = create_test_customer(client)
    _, manager_headers = manager
    _, mechanic_headers = mechanic
    created = client.post(
        "/service-tickets", json=make_ticket_payload(customer_id), headers=manager_headers
    ).json

    response = client.put(
        f"/service-tickets/{created['id']}/status",
        json={"status": "In Progress"},
        headers=mechanic_headers,
    )

    assert response.status_code == 200
    assert response.json["status"] == "In Progress"


def test_update_ticket_status_rejects_invalid_value(client, manager, mechanic):
    """PUT /service-tickets/<id>/status should reject a status
    outside the five recognized values."""
    customer_id = create_test_customer(client)
    _, manager_headers = manager
    _, mechanic_headers = mechanic
    created = client.post(
        "/service-tickets", json=make_ticket_payload(customer_id), headers=manager_headers
    ).json

    response = client.put(
        f"/service-tickets/{created['id']}/status",
        json={"status": "Abandoned"},
        headers=mechanic_headers,
    )

    assert response.status_code == 400


def test_update_ticket_status_requires_token(client, manager):
    """PUT /service-tickets/<id>/status should return 401 with no
    Authorization header."""
    customer_id = create_test_customer(client)
    _, manager_headers = manager
    created = client.post(
        "/service-tickets", json=make_ticket_payload(customer_id), headers=manager_headers
    ).json

    response = client.put(
        f"/service-tickets/{created['id']}/status", json={"status": "Paid"}
    )

    assert response.status_code == 401


def test_assign_mechanic_to_ticket(client, manager, mechanic):
    """PUT /service-tickets/<id>/assign-mechanic/<id> should add the
    mechanic to the ticket's list of assigned mechanics. Manager-only."""
    customer_id = create_test_customer(client)
    _, manager_headers = manager
    mechanic_id, _ = mechanic
    ticket_id = client.post(
        "/service-tickets", json=make_ticket_payload(customer_id), headers=manager_headers
    ).json["id"]

    response = client.put(
        f"/service-tickets/{ticket_id}/assign-mechanic/{mechanic_id}",
        headers=manager_headers,
    )

    assert response.status_code == 200
    assert mechanic_id in response.json["mechanic_ids"]


def test_assign_mechanic_rejects_regular_mechanic(client, manager, mechanic):
    """A regular mechanic may not assign mechanics to a ticket."""
    customer_id = create_test_customer(client)
    _, manager_headers = manager
    mechanic_id, mechanic_headers = mechanic
    ticket_id = client.post(
        "/service-tickets", json=make_ticket_payload(customer_id), headers=manager_headers
    ).json["id"]

    response = client.put(
        f"/service-tickets/{ticket_id}/assign-mechanic/{mechanic_id}",
        headers=mechanic_headers,
    )

    assert response.status_code == 403


def test_assign_mechanic_rejects_duplicate_assignment(client, manager, mechanic):
    """Assigning the same mechanic to the same ticket twice should be
    rejected, not silently create a duplicate link."""
    customer_id = create_test_customer(client)
    _, manager_headers = manager
    mechanic_id, _ = mechanic
    ticket_id = client.post(
        "/service-tickets", json=make_ticket_payload(customer_id), headers=manager_headers
    ).json["id"]

    client.put(
        f"/service-tickets/{ticket_id}/assign-mechanic/{mechanic_id}",
        headers=manager_headers,
    )
    response = client.put(
        f"/service-tickets/{ticket_id}/assign-mechanic/{mechanic_id}",
        headers=manager_headers,
    )

    assert response.status_code == 400


def test_assign_mechanic_ticket_not_found(client, manager, mechanic):
    """Assigning a mechanic to a ticket id that doesn't exist should
    return a 404."""
    _, manager_headers = manager
    mechanic_id, _ = mechanic

    response = client.put(
        f"/service-tickets/999/assign-mechanic/{mechanic_id}", headers=manager_headers
    )

    assert response.status_code == 404


def test_assign_mechanic_mechanic_not_found(client, manager):
    """Assigning a mechanic id that doesn't exist should return a 404."""
    customer_id = create_test_customer(client)
    _, manager_headers = manager
    ticket_id = client.post(
        "/service-tickets", json=make_ticket_payload(customer_id), headers=manager_headers
    ).json["id"]

    response = client.put(
        f"/service-tickets/{ticket_id}/assign-mechanic/999", headers=manager_headers
    )

    assert response.status_code == 404


def test_remove_mechanic_from_ticket(client, manager, mechanic):
    """PUT /service-tickets/<id>/remove-mechanic/<id> should remove a
    previously assigned mechanic. Manager-only."""
    customer_id = create_test_customer(client)
    _, manager_headers = manager
    mechanic_id, _ = mechanic
    ticket_id = client.post(
        "/service-tickets", json=make_ticket_payload(customer_id), headers=manager_headers
    ).json["id"]
    client.put(
        f"/service-tickets/{ticket_id}/assign-mechanic/{mechanic_id}",
        headers=manager_headers,
    )

    response = client.put(
        f"/service-tickets/{ticket_id}/remove-mechanic/{mechanic_id}",
        headers=manager_headers,
    )

    assert response.status_code == 200
    assert mechanic_id not in response.json["mechanic_ids"]


def test_remove_mechanic_rejects_when_not_assigned(client, manager, mechanic):
    """Removing a mechanic who was never assigned to the ticket
    should be rejected, not silently succeed."""
    customer_id = create_test_customer(client)
    _, manager_headers = manager
    mechanic_id, _ = mechanic
    ticket_id = client.post(
        "/service-tickets", json=make_ticket_payload(customer_id), headers=manager_headers
    ).json["id"]

    response = client.put(
        f"/service-tickets/{ticket_id}/remove-mechanic/{mechanic_id}",
        headers=manager_headers,
    )

    assert response.status_code == 400


def test_remove_mechanic_ticket_not_found(client, manager, mechanic):
    """Removing a mechanic from a ticket id that doesn't exist should
    return a 404."""
    _, manager_headers = manager
    mechanic_id, _ = mechanic

    response = client.put(
        f"/service-tickets/999/remove-mechanic/{mechanic_id}", headers=manager_headers
    )

    assert response.status_code == 404


def test_remove_mechanic_mechanic_not_found(client, manager):
    """Removing a mechanic id that doesn't exist should return a 404."""
    customer_id = create_test_customer(client)
    _, manager_headers = manager
    ticket_id = client.post(
        "/service-tickets", json=make_ticket_payload(customer_id), headers=manager_headers
    ).json["id"]

    response = client.put(
        f"/service-tickets/{ticket_id}/remove-mechanic/999", headers=manager_headers
    )

    assert response.status_code == 404


def test_edit_ticket_mechanics_bulk_add_and_remove(client, manager, mechanic):
    """PUT /service-tickets/<id>/edit should add and remove mechanics
    in one request via add_ids/remove_ids."""
    customer_id = create_test_customer(client)
    _, manager_headers = manager
    mechanic_id, _ = mechanic
    other_id, _ = create_mechanic(client, manager_headers, index=2)
    ticket_id = client.post(
        "/service-tickets", json=make_ticket_payload(customer_id), headers=manager_headers
    ).json["id"]
    client.put(
        f"/service-tickets/{ticket_id}/assign-mechanic/{mechanic_id}",
        headers=manager_headers,
    )

    response = client.put(
        f"/service-tickets/{ticket_id}/edit",
        json={"add_ids": [other_id], "remove_ids": [mechanic_id]},
        headers=manager_headers,
    )

    assert response.status_code == 200
    assert other_id in response.json["mechanic_ids"]
    assert mechanic_id not in response.json["mechanic_ids"]


def test_edit_ticket_mechanics_is_idempotent_on_redundancy(client, manager, mechanic):
    """Adding an already-assigned mechanic, or removing one who isn't
    assigned, is silently skipped rather than rejected -- appropriate
    for a bulk operation."""
    customer_id = create_test_customer(client)
    _, manager_headers = manager
    mechanic_id, _ = mechanic
    ticket_id = client.post(
        "/service-tickets", json=make_ticket_payload(customer_id), headers=manager_headers
    ).json["id"]
    client.put(
        f"/service-tickets/{ticket_id}/assign-mechanic/{mechanic_id}",
        headers=manager_headers,
    )

    response = client.put(
        f"/service-tickets/{ticket_id}/edit",
        json={"add_ids": [mechanic_id], "remove_ids": []},
        headers=manager_headers,
    )

    assert response.status_code == 200
    assert mechanic_id in response.json["mechanic_ids"]


def test_edit_ticket_mechanics_rejects_nonexistent_mechanic_id(client, manager):
    """A mechanic id that doesn't exist at all in add_ids or
    remove_ids is a real 404, unlike redundant-but-valid ids."""
    customer_id = create_test_customer(client)
    _, manager_headers = manager
    ticket_id = client.post(
        "/service-tickets", json=make_ticket_payload(customer_id), headers=manager_headers
    ).json["id"]

    response = client.put(
        f"/service-tickets/{ticket_id}/edit",
        json={"add_ids": [999999], "remove_ids": []},
        headers=manager_headers,
    )

    assert response.status_code == 404


def test_edit_ticket_mechanics_rejects_regular_mechanic(client, manager, mechanic):
    """A regular mechanic may not bulk-edit a ticket's mechanics."""
    customer_id = create_test_customer(client)
    _, manager_headers = manager
    _, mechanic_headers = mechanic
    ticket_id = client.post(
        "/service-tickets", json=make_ticket_payload(customer_id), headers=manager_headers
    ).json["id"]

    response = client.put(
        f"/service-tickets/{ticket_id}/edit",
        json={"add_ids": [], "remove_ids": []},
        headers=mechanic_headers,
    )

    assert response.status_code == 403


def test_edit_ticket_mechanics_ticket_not_found(client, manager):
    """PUT /service-tickets/<id>/edit should return a 404 for a
    ticket id that doesn't exist."""
    _, manager_headers = manager

    response = client.put(
        "/service-tickets/999/edit",
        json={"add_ids": [], "remove_ids": []},
        headers=manager_headers,
    )

    assert response.status_code == 404
