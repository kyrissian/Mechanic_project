"""Tests for PUT /service-tickets/<id>/add-part/<inventory_id>."""

from tests.conftest import create_part, create_ticket, make_inventory_payload


def test_add_part_as_manager(client, manager):
    """A manager can add a part; quantity defaults to 1, the catalog
    price is recorded on the line, and stock decrements."""
    _, manager_headers = manager
    ticket_id = create_ticket(client, manager_headers)
    part_id = create_part(client, manager_headers)

    response = client.put(
        f"/service-tickets/{ticket_id}/add-part/{part_id}", headers=manager_headers
    )

    assert response.status_code == 200
    assert len(response.json["parts"]) == 1
    line = response.json["parts"][0]
    assert line["inventory_id"] == part_id
    assert line["name"] == "Oil Filter"
    assert line["quantity"] == 1
    assert line["unit_price"] == "12.50"
    assert line["line_total"] == "12.50"

    part = client.get(f"/inventory/{part_id}", headers=manager_headers).json
    assert part["quantity_on_hand"] == 19  # started at 20


def test_add_part_as_assigned_mechanic(client, manager, mechanic):
    """A mechanic assigned to the ticket can add a part."""
    _, manager_headers = manager
    mechanic_id, mechanic_headers = mechanic
    ticket_id = create_ticket(client, manager_headers)
    part_id = create_part(client, manager_headers)
    client.put(
        f"/service-tickets/{ticket_id}/assign-mechanic/{mechanic_id}",
        headers=manager_headers,
    )

    response = client.put(
        f"/service-tickets/{ticket_id}/add-part/{part_id}", headers=mechanic_headers
    )

    assert response.status_code == 200
    assert response.json["parts"][0]["inventory_id"] == part_id


def test_add_part_rejects_unassigned_mechanic(client, manager, mechanic):
    """A mechanic who is NOT assigned to the ticket gets a 403."""
    _, manager_headers = manager
    _, mechanic_headers = mechanic
    ticket_id = create_ticket(client, manager_headers)
    part_id = create_part(client, manager_headers)

    response = client.put(
        f"/service-tickets/{ticket_id}/add-part/{part_id}", headers=mechanic_headers
    )

    assert response.status_code == 403


def test_add_part_requires_token(client, manager):
    """The add-part route returns 401 with no Authorization header."""
    _, manager_headers = manager
    ticket_id = create_ticket(client, manager_headers)
    part_id = create_part(client, manager_headers)

    response = client.put(f"/service-tickets/{ticket_id}/add-part/{part_id}")

    assert response.status_code == 401


def test_add_part_custom_quantity(client, manager):
    """A quantity in the body is honored, reflected in line_total,
    and decremented from stock."""
    _, manager_headers = manager
    ticket_id = create_ticket(client, manager_headers)
    part_id = create_part(client, manager_headers)

    response = client.put(
        f"/service-tickets/{ticket_id}/add-part/{part_id}",
        json={"quantity": 3},
        headers=manager_headers,
    )

    assert response.status_code == 200
    line = response.json["parts"][0]
    assert line["quantity"] == 3
    assert line["line_total"] == "37.50"

    part = client.get(f"/inventory/{part_id}", headers=manager_headers).json
    assert part["quantity_on_hand"] == 17  # started at 20


def test_add_part_again_bumps_quantity_and_decrements_further(client, manager):
    """Adding a part already on the ticket increases its quantity
    instead of creating a second line, and stock decrements again."""
    _, manager_headers = manager
    ticket_id = create_ticket(client, manager_headers)
    part_id = create_part(client, manager_headers)
    url = f"/service-tickets/{ticket_id}/add-part/{part_id}"

    client.put(url, headers=manager_headers)
    response = client.put(url, json={"quantity": 2}, headers=manager_headers)

    assert response.status_code == 200
    assert len(response.json["parts"]) == 1
    assert response.json["parts"][0]["quantity"] == 3

    part = client.get(f"/inventory/{part_id}", headers=manager_headers).json
    assert part["quantity_on_hand"] == 17  # 20 - 1 - 2


def test_add_part_rejects_invalid_quantity(client, manager):
    """A quantity below 1 is rejected with validation details."""
    _, manager_headers = manager
    ticket_id = create_ticket(client, manager_headers)
    part_id = create_part(client, manager_headers)

    response = client.put(
        f"/service-tickets/{ticket_id}/add-part/{part_id}",
        json={"quantity": 0},
        headers=manager_headers,
    )

    assert response.status_code == 400
    assert "quantity" in response.json["details"]


def test_add_part_rejects_over_allocation(client, manager):
    """Requesting more of a part than the shop has in stock is
    rejected with a 400 naming how many are actually available, and
    stock is left unchanged."""
    _, manager_headers = manager
    ticket_id = create_ticket(client, manager_headers)
    part_id = create_part(client, manager_headers, quantity_on_hand=3)

    response = client.put(
        f"/service-tickets/{ticket_id}/add-part/{part_id}",
        json={"quantity": 4},
        headers=manager_headers,
    )

    assert response.status_code == 400
    assert "3 available" in response.json["error"]

    part = client.get(f"/inventory/{part_id}", headers=manager_headers).json
    assert part["quantity_on_hand"] == 3  # unchanged


def test_add_part_ticket_not_found(client, manager):
    """Adding a part to a ticket that doesn't exist is a 404."""
    _, manager_headers = manager
    part_id = create_part(client, manager_headers)

    response = client.put(
        f"/service-tickets/999/add-part/{part_id}", headers=manager_headers
    )

    assert response.status_code == 404


def test_add_part_part_not_found(client, manager):
    """Adding a part that doesn't exist is a 404."""
    _, manager_headers = manager
    ticket_id = create_ticket(client, manager_headers)

    response = client.put(
        f"/service-tickets/{ticket_id}/add-part/999", headers=manager_headers
    )

    assert response.status_code == 404


def test_price_change_does_not_alter_existing_line(client, manager):
    """Repricing a part later must not change the unit_price already
    recorded on an existing ticket line."""
    _, manager_headers = manager
    ticket_id = create_ticket(client, manager_headers)
    part_id = create_part(client, manager_headers)
    client.put(
        f"/service-tickets/{ticket_id}/add-part/{part_id}", headers=manager_headers
    )

    client.put(
        f"/inventory/{part_id}",
        json=make_inventory_payload(price="20.00"),
        headers=manager_headers,
    )

    ticket = client.get(f"/service-tickets/{ticket_id}", headers=manager_headers).json
    catalog = client.get(f"/inventory/{part_id}", headers=manager_headers).json
    assert ticket["parts"][0]["unit_price"] == "12.50"
    assert catalog["price"] == "20.00"
