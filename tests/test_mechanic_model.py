"""Tests for the Mechanic model, including its many-to-many
relationship with ServiceTicket."""

from decimal import Decimal

from app.models.customer import Customer
from app.models.mechanic import Mechanic
from app.models.service_ticket import ServiceTicket
from tests.conftest import (
    make_customer_kwargs,
    make_mechanic_kwargs,
    make_service_ticket_kwargs,
)


def test_create_mechanic(db):
    """A Mechanic with all fields set should save and be retrievable
    with those exact values intact."""
    mechanic = Mechanic(**make_mechanic_kwargs())
    db.session.add(mechanic)
    db.session.commit()

    saved = db.session.get(Mechanic, mechanic.id)

    assert saved is not None
    assert saved.name == "Alex Chen"
    assert saved.email == "alex@example.com"
    assert saved.phone == "555-987-6543"
    assert saved.salary == Decimal("55000.00")
    assert saved.role == "mechanic"


def test_mechanic_can_be_assigned_to_multiple_tickets(db):
    """A single mechanic should be able to work on more than one
    service ticket -- this is the many-to-many relationship the ERD's
    service_mechanics junction table exists to support."""
    customer = Customer(**make_customer_kwargs())
    mechanic = Mechanic(**make_mechanic_kwargs())

    ticket_one = ServiceTicket(customer=customer, **make_service_ticket_kwargs())
    ticket_two = ServiceTicket(
        customer=customer,
        **make_service_ticket_kwargs(vin="2T1BURHE0JC014678", service_desc="Oil change"),
    )

    ticket_one.mechanics.append(mechanic)
    ticket_two.mechanics.append(mechanic)

    db.session.add_all([customer, mechanic, ticket_one, ticket_two])
    db.session.commit()

    saved_mechanic = db.session.get(Mechanic, mechanic.id)
    assert len(saved_mechanic.service_tickets) == 2
