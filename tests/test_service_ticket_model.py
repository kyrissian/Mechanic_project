"""Tests for the ServiceTicket model, including its relationship to
Customer and its many-to-many relationship with Mechanic."""

from app.models.customer import Customer
from app.models.mechanic import Mechanic
from app.models.service_ticket import ServiceTicket
from tests.conftest import make_customer_kwargs, make_service_ticket_kwargs


def test_create_service_ticket_linked_to_customer(db):
    """A ServiceTicket should save with its VIN/date/description
    intact, and be linked back to the customer that owns it."""
    customer = Customer(**make_customer_kwargs())
    db.session.add(customer)
    db.session.commit()

    ticket = ServiceTicket(customer_id=customer.id, **make_service_ticket_kwargs())
    db.session.add(ticket)
    db.session.commit()

    saved = db.session.get(ServiceTicket, ticket.id)

    assert saved is not None
    assert saved.vin == "1HGCM82633A004352"
    assert saved.service_desc == "Brake pad replacement"
    assert saved.customer.id == customer.id
    assert saved.customer.name == "Jamie Rivera"


def test_service_ticket_can_have_multiple_mechanics(db):
    """A single ticket should be able to require more than one
    mechanic -- the other direction of the same many-to-many
    relationship tested in test_mechanic_model.py."""
    customer = Customer(**make_customer_kwargs())
    mechanic_one = Mechanic(
        name="Alex Chen", email="alex@example.com", phone="555-987-6543", salary=55000.00
    )
    mechanic_two = Mechanic(
        name="Sam Diaz", email="sam@example.com", phone="555-222-3333", salary=58000.00
    )

    ticket = ServiceTicket(customer=customer, **make_service_ticket_kwargs())
    ticket.mechanics.extend([mechanic_one, mechanic_two])

    db.session.add_all([customer, mechanic_one, mechanic_two, ticket])
    db.session.commit()

    saved = db.session.get(ServiceTicket, ticket.id)
    assert len(saved.mechanics) == 2
    assert {m.name for m in saved.mechanics} == {"Alex Chen", "Sam Diaz"}
