"""Tests for the Inventory CRUD routes and their role-based access rules."""

from tests.conftest import (
    create_part,
    create_ticket,
    login_customer,
    make_inventory_payload,
)


def test_create_part_requires_manager(client, manager):
    """POST /inventory should succeed for a manager."""
    _, manager_headers = manager

    response = client.post(
        "/inventory", json=make_inventory_payload(), headers=manager_headers
    )

    assert response.status_code == 201
    assert response.json["name"] == "Oil Filter"
    assert response.json["price"] == "12.50"
    assert response.json["quantity_on_hand"] == 20
    assert "id" in response.json


def test_create_part_rejects_regular_mechanic(client, mechanic):
    """A regular mechanic may not add parts to the catalog."""
    _, mechanic_headers = mechanic

    response = client.post(
        "/inventory", json=make_inventory_payload(), headers=mechanic_headers
    )

    assert response.status_code == 403


def test_create_part_requires_token(client):
    """POST /inventory should return 401 with no Authorization header."""
    response = client.post("/inventory", json=make_inventory_payload())

    assert response.status_code == 401


def test_create_part_rejects_duplicate_name(client, manager):
    """A second part with the same name is rejected, ignoring case."""
    _, manager_headers = manager
    client.post("/inventory", json=make_inventory_payload(), headers=manager_headers)

    response = client.post(
        "/inventory",
        json=make_inventory_payload(name="oil filter"),
        headers=manager_headers,
    )

    assert response.status_code == 400
    assert "error" in response.json


def test_create_part_rejects_missing_price(client, manager):
    """POST /inventory should return a 400 when price is missing."""
    _, manager_headers = manager

    response = client.post(
        "/inventory",
        json={"name": "Oil Filter", "quantity_on_hand": 10},
        headers=manager_headers,
    )

    assert response.status_code == 400
    assert "price" in response.json["details"]


def test_create_part_rejects_non_positive_price(client, manager):
    """A zero or negative price is rejected."""
    _, manager_headers = manager

    for bad_price in ("0", "-5.00"):
        response = client.post(
            "/inventory",
            json=make_inventory_payload(price=bad_price),
            headers=manager_headers,
        )

        assert response.status_code == 400
        assert "price" in response.json["details"]


def test_create_part_rejects_missing_quantity_on_hand(client, manager):
    """POST /inventory should return a 400 when quantity_on_hand is
    missing -- a manager must state stock explicitly."""
    _, manager_headers = manager

    response = client.post(
        "/inventory",
        json={"name": "Oil Filter", "price": "12.50"},
        headers=manager_headers,
    )

    assert response.status_code == 400
    assert "quantity_on_hand" in response.json["details"]


def test_create_part_rejects_negative_quantity_on_hand(client, manager):
    """A negative quantity_on_hand is rejected."""
    _, manager_headers = manager

    response = client.post(
        "/inventory",
        json=make_inventory_payload(quantity_on_hand=-1),
        headers=manager_headers,
    )

    assert response.status_code == 400
    assert "quantity_on_hand" in response.json["details"]


def test_get_inventory_any_mechanic(client, manager, mechanic):
    """GET /inventory should be readable by a regular mechanic, and
    should be paginated."""
    _, manager_headers = manager
    _, mechanic_headers = mechanic
    create_part(client, manager_headers)
    create_part(client, manager_headers, index=2)

    response = client.get("/inventory", headers=mechanic_headers)

    assert response.status_code == 200
    assert len(response.json["inventory"]) == 2
    assert response.json["total"] == 2


def test_get_inventory_requires_token(client):
    """GET /inventory should return 401 with no Authorization header."""
    response = client.get("/inventory")

    assert response.status_code == 401


def test_get_inventory_rejects_customer_token(client):
    """A valid CUSTOMER token must not open a mechanic-only route."""
    _, customer_headers = login_customer(client)

    response = client.get("/inventory", headers=customer_headers)

    assert response.status_code == 401


def test_get_single_part(client, manager):
    """GET /inventory/<id> should return that part, including stock."""
    _, manager_headers = manager
    part_id = create_part(client, manager_headers)

    response = client.get(f"/inventory/{part_id}", headers=manager_headers)

    assert response.status_code == 200
    assert response.json["name"] == "Oil Filter"
    assert response.json["quantity_on_hand"] == 20


def test_get_single_part_not_found(client, manager):
    """GET /inventory/<id> should return a 404 for an unknown id."""
    _, manager_headers = manager

    response = client.get("/inventory/999", headers=manager_headers)

    assert response.status_code == 404


def test_update_part_manager(client, manager):
    """PUT /inventory/<id> should update the part for a manager,
    including its stock count."""
    _, manager_headers = manager
    part_id = create_part(client, manager_headers)

    response = client.put(
        f"/inventory/{part_id}",
        json=make_inventory_payload(
            name="Premium Oil Filter", price="15.00", quantity_on_hand=5
        ),
        headers=manager_headers,
    )

    assert response.status_code == 200
    assert response.json["name"] == "Premium Oil Filter"
    assert response.json["price"] == "15.00"
    assert response.json["quantity_on_hand"] == 5


def test_update_part_allows_keeping_own_name(client, manager):
    """Changing only the price, and keeping the same name, is not a
    duplicate-name conflict."""
    _, manager_headers = manager
    part_id = create_part(client, manager_headers)

    response = client.put(
        f"/inventory/{part_id}",
        json=make_inventory_payload(price="14.00"),
        headers=manager_headers,
    )

    assert response.status_code == 200


def test_update_part_rejects_regular_mechanic(client, manager, mechanic):
    """A regular mechanic may not edit the catalog."""
    _, manager_headers = manager
    _, mechanic_headers = mechanic
    part_id = create_part(client, manager_headers)

    response = client.put(
        f"/inventory/{part_id}",
        json=make_inventory_payload(price="1.00"),
        headers=mechanic_headers,
    )

    assert response.status_code == 403


def test_update_part_rejects_duplicate_name(client, manager):
    """Renaming a part to another part's name is rejected."""
    _, manager_headers = manager
    create_part(client, manager_headers)
    other_id = create_part(client, manager_headers, index=2)

    response = client.put(
        f"/inventory/{other_id}",
        json=make_inventory_payload(name="Oil Filter"),
        headers=manager_headers,
    )

    assert response.status_code == 400


def test_update_part_not_found(client, manager):
    """PUT /inventory/<id> should return a 404 for an unknown id."""
    _, manager_headers = manager

    response = client.put(
        "/inventory/999", json=make_inventory_payload(), headers=manager_headers
    )

    assert response.status_code == 404


def test_delete_part_manager(client, manager):
    """DELETE /inventory/<id> should remove an unused part for a manager."""
    _, manager_headers = manager
    part_id = create_part(client, manager_headers)

    response = client.delete(f"/inventory/{part_id}", headers=manager_headers)

    assert response.status_code == 200
    assert client.get(f"/inventory/{part_id}", headers=manager_headers).status_code == 404


def test_delete_part_rejects_regular_mechanic(client, manager, mechanic):
    """A regular mechanic may not delete parts."""
    _, manager_headers = manager
    _, mechanic_headers = mechanic
    part_id = create_part(client, manager_headers)

    response = client.delete(f"/inventory/{part_id}", headers=mechanic_headers)

    assert response.status_code == 403


def test_delete_part_not_found(client, manager):
    """DELETE /inventory/<id> should return a 404 for an unknown id."""
    _, manager_headers = manager

    response = client.delete("/inventory/999", headers=manager_headers)

    assert response.status_code == 404


def test_delete_part_blocked_when_used_on_a_ticket(client, manager):
    """A part that has been used on a ticket can't be deleted (409),
    so the ticket's history stays intact."""
    _, manager_headers = manager
    part_id = create_part(client, manager_headers)
    ticket_id = create_ticket(client, manager_headers)
    client.put(
        f"/service-tickets/{ticket_id}/add-part/{part_id}", headers=manager_headers
    )

    response = client.delete(f"/inventory/{part_id}", headers=manager_headers)

    assert response.status_code == 409
    assert client.get(f"/inventory/{part_id}", headers=manager_headers).status_code == 200
