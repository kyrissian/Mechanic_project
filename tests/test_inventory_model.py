"""Tests for the Inventory model and the TicketPart junction model."""

from decimal import Decimal

import pytest
from sqlalchemy.exc import IntegrityError

from app.models.customer import Customer
from app.models.inventory import Inventory
from app.models.service_ticket import ServiceTicket
from app.models.ticket_part import TicketPart
from tests.conftest import make_customer_kwargs, make_service_ticket_kwargs


def test_create_inventory_part(db):
    """A part should save and be retrievable with its price as an
    exact Decimal and its stock count intact."""
    part = Inventory(name="Oil Filter", price=Decimal("12.50"), quantity_on_hand=20)
    db.session.add(part)
    db.session.commit()

    saved = db.session.get(Inventory, part.id)

    assert saved is not None
    assert saved.name == "Oil Filter"
    assert saved.price == Decimal("12.50")
    assert saved.quantity_on_hand == 20


def test_inventory_name_must_be_unique(db):
    """Two parts can't share a name -- the second insert should fail
    at the database level."""
    db.session.add(
        Inventory(name="Oil Filter", price=Decimal("12.50"), quantity_on_hand=20)
    )
    db.session.commit()

    db.session.add(
        Inventory(name="Oil Filter", price=Decimal("9.99"), quantity_on_hand=5)
    )

    with pytest.raises(IntegrityError):
        db.session.commit()
    db.session.rollback()


def test_ticket_part_links_ticket_and_part(db):
    """A TicketPart should link a ticket to a part, carrying its own
    quantity and the unit price recorded when it was added."""
    customer = Customer(**make_customer_kwargs())
    ticket = ServiceTicket(customer=customer, **make_service_ticket_kwargs())
    part = Inventory(name="Oil Filter", price=Decimal("12.50"), quantity_on_hand=20)
    line = TicketPart(ticket=ticket, part=part, quantity=2, unit_price=Decimal("12.50"))

    db.session.add_all([customer, ticket, part, line])
    db.session.commit()

    saved = db.session.get(ServiceTicket, ticket.id)
    assert len(saved.ticket_parts) == 1
    assert saved.ticket_parts[0].part.name == "Oil Filter"
    assert saved.ticket_parts[0].quantity == 2
    assert saved.ticket_parts[0].unit_price == Decimal("12.50")
