"""Tests for the mechanic ticket-count sort/insight endpoints:
most-tickets, open-tickets, closed-tickets."""

from app.models.customer import Customer
from app.models.mechanic import Mechanic
from app.models.service_ticket import ServiceTicket
from tests.conftest import create_mechanic, make_customer_kwargs, make_service_ticket_kwargs


def _seed_customer(db):
    customer = Customer(**make_customer_kwargs())
    db.session.add(customer)
    db.session.commit()
    return customer


def _make_ticket(db, customer, mechanic_obj, status, **overrides):
    ticket = ServiceTicket(
        customer=customer, status=status, **make_service_ticket_kwargs(**overrides)
    )
    ticket.mechanics.append(mechanic_obj)
    db.session.add(ticket)
    db.session.commit()
    return ticket


def test_most_tickets_requires_authentication(client):
    """GET /mechanics/most-tickets should return 401 with no token."""
    response = client.get("/mechanics/most-tickets")

    assert response.status_code == 401


def test_most_tickets_sorted_descending_by_default(client, db, manager, mechanic):
    """Mechanics should be sorted by total ticket count, most first,
    and the response must never include salary."""
    customer = _seed_customer(db)
    _, manager_headers = manager
    mechanic_id, mechanic_headers = mechanic
    create_mechanic(client, manager_headers, index=2)

    busy = db.session.get(Mechanic, mechanic_id)
    _make_ticket(db, customer, busy, "Pending", vin="1HGCM82633A004352")
    _make_ticket(db, customer, busy, "Pending", vin="2T1BURHE0JC014678")

    response = client.get("/mechanics/most-tickets", headers=mechanic_headers)

    assert response.status_code == 200
    assert response.json[0]["id"] == mechanic_id
    assert response.json[0]["ticket_count"] == 2
    assert "salary" not in response.json[0]


def test_most_tickets_order_asc(client, db, manager, mechanic):
    """?order=asc should reverse the sort to least tickets first.
    Asserts relative order (quiet mechanic before the busy one)
    rather than an absolute index -- the roster also includes the
    manager account itself (0 tickets, tied with the quiet mechanic),
    so index [0] isn't reliably the mechanic this test cares about.
    """
    customer = _seed_customer(db)
    _, manager_headers = manager
    mechanic_id, mechanic_headers = mechanic
    quiet_id, _ = create_mechanic(client, manager_headers, index=2)

    busy = db.session.get(Mechanic, mechanic_id)
    _make_ticket(db, customer, busy, "Pending")

    response = client.get("/mechanics/most-tickets?order=asc", headers=mechanic_headers)

    assert response.status_code == 200
    ids_in_order = [m["id"] for m in response.json]
    assert ids_in_order.index(quiet_id) < ids_in_order.index(mechanic_id)


def test_open_tickets_only_counts_open_statuses(client, db, mechanic):
    """open-tickets should count Pending/In Progress/Completed, not
    Paid or Picked Up."""
    customer = _seed_customer(db)
    mechanic_id, mechanic_headers = mechanic
    mech = db.session.get(Mechanic, mechanic_id)

    _make_ticket(db, customer, mech, "Pending", vin="1HGCM82633A004352")
    _make_ticket(db, customer, mech, "Paid", vin="2T1BURHE0JC014678")

    response = client.get("/mechanics/open-tickets", headers=mechanic_headers)

    assert response.status_code == 200
    mine = next(m for m in response.json if m["id"] == mechanic_id)
    assert mine["open_ticket_count"] == 1


def test_closed_tickets_only_counts_closed_statuses(client, db, mechanic):
    """closed-tickets should count Paid/Picked Up, not the open statuses."""
    customer = _seed_customer(db)
    mechanic_id, mechanic_headers = mechanic
    mech = db.session.get(Mechanic, mechanic_id)

    _make_ticket(db, customer, mech, "Picked Up", vin="1HGCM82633A004352")
    _make_ticket(db, customer, mech, "Pending", vin="2T1BURHE0JC014678")

    response = client.get("/mechanics/closed-tickets", headers=mechanic_headers)

    assert response.status_code == 200
    mine = next(m for m in response.json if m["id"] == mechanic_id)
    assert mine["closed_ticket_count"] == 1
