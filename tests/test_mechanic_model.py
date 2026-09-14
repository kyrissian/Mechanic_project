"""Tests for the Mechanic model, including its many-to-many
relationship with ServiceTicket."""

from app.models.customer import Customer
from app.models.mechanic import Mechanic
from app.models.service_ticket import ServiceTicket
from tests.conftest import make_service_ticket_kwargs


def test_create_mechanic(db):
    """A Mechanic with all fields set should save and be retrievable
    with those exact values intact."""
    mechanic = Mechanic(
        name="Alex Chen",
        phone="555-987-6543",
        address="456 Shop Rd",
        salary=55000,
    )
    db.session.add(mechanic)
    db.session.commit()

    saved = db.session.get(Mechanic, mechanic.id)

    assert saved is not None
    assert saved.name == "Alex Chen"
    assert saved.phone == "555-987-6543"
    assert saved.address == "456 Shop Rd"
    assert saved.salary == 55000


def test_mechanic_can_be_assigned_to_multiple_tickets(db):
    """A single mechanic should be able to work on more than one
    service ticket -- this is the many-to-many relationship the ERD's
    ST_Mechanic junction table exists to support."""
    customer = Customer(
        first_name="Jamie", last_name="Rivera", email="jamie@example.com"
    )
    mechanic = Mechanic(
        name="Alex Chen", phone="555-987-6543", address="456 Shop Rd", salary=55000
    )

    ticket_one = ServiceTicket(customer=customer, **make_service_ticket_kwargs())
    ticket_two = ServiceTicket(
        customer=customer,
        **make_service_ticket_kwargs(model="Corolla", vin="2T1BURHE0JC014678"),
    )

    ticket_one.mechanics.append(mechanic)
    ticket_two.mechanics.append(mechanic)

    db.session.add_all([customer, mechanic, ticket_one, ticket_two])
    db.session.commit()

    saved_mechanic = db.session.get(Mechanic, mechanic.id)
    assert len(saved_mechanic.service_tickets) == 2
