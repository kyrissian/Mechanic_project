"""Tests for the ServiceTicket model, including its relationship to
Customer and its many-to-many relationship with Mechanic."""

from app.models.customer import Customer
from app.models.mechanic import Mechanic
from app.models.service_ticket import ServiceTicket
from tests.conftest import make_service_ticket_kwargs


def test_create_service_ticket_linked_to_customer(db):
    """A ServiceTicket should save with all its vehicle/work fields
    intact, and be linked back to the customer that owns it."""
    customer = Customer(
        first_name="Jamie", last_name="Rivera", email="jamie@example.com"
    )
    db.session.add(customer)
    db.session.commit()

    ticket = ServiceTicket(
        customer_id=customer.id,
        work_description="Brake pad replacement",
        **make_service_ticket_kwargs(),
    )
    db.session.add(ticket)
    db.session.commit()

    saved = db.session.get(ServiceTicket, ticket.id)

    assert saved is not None
    assert saved.make == "Honda"
    assert saved.vin == "1HGCM82633A004352"
    assert saved.customer.id == customer.id
    assert saved.customer.first_name == "Jamie"


def test_service_ticket_can_have_multiple_mechanics(db):
    """A single ticket should be able to require more than one
    mechanic -- the other direction of the same many-to-many
    relationship tested in test_mechanic_model.py."""
    customer = Customer(
        first_name="Jamie", last_name="Rivera", email="jamie@example.com"
    )
    mechanic_one = Mechanic(
        name="Alex Chen", phone="555-987-6543", address="456 Shop Rd", salary=55000
    )
    mechanic_two = Mechanic(
        name="Sam Diaz", phone="555-222-3333", address="789 Garage Ln", salary=58000
    )

    ticket = ServiceTicket(customer=customer, **make_service_ticket_kwargs())
    ticket.mechanics.extend([mechanic_one, mechanic_two])

    db.session.add_all([customer, mechanic_one, mechanic_two, ticket])
    db.session.commit()

    saved = db.session.get(ServiceTicket, ticket.id)
    assert len(saved.mechanics) == 2
    assert {m.name for m in saved.mechanics} == {"Alex Chen", "Sam Diaz"}
