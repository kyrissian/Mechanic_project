"""Tests for the service_mechanics junction table itself -- the
composite primary key that enforces one row per (ticket, mechanic)
pair at the database level, as a backstop below the app-level
duplicate check in assign_mechanic."""

import pytest
from sqlalchemy.exc import IntegrityError

from app.models.customer import Customer
from app.models.mechanic import Mechanic
from app.models.service_mechanics import service_mechanics
from app.models.service_ticket import ServiceTicket
from tests.conftest import (
    make_customer_kwargs,
    make_mechanic_kwargs,
    make_service_ticket_kwargs,
)


def test_duplicate_service_mechanics_row_rejected_at_db_level(db):
    """The composite primary key on service_mechanics should reject a
    second row for the same (ticket_id, mechanic_id) pair, even if
    something bypassed the application-level duplicate check in
    assign_mechanic (e.g. a direct insert, or a race between two
    near-simultaneous requests)."""
    customer = Customer(**make_customer_kwargs())
    mechanic = Mechanic(**make_mechanic_kwargs())
    ticket = ServiceTicket(customer=customer, **make_service_ticket_kwargs())
    db.session.add_all([customer, mechanic, ticket])
    db.session.commit()

    # Insert directly into the junction table, bypassing the ORM
    # relationship (ticket.mechanics.append(...)) and its app-level
    # duplicate check entirely -- this is exactly the scenario the
    # composite primary key exists to guard against even when the
    # application layer doesn't catch it.
    db.session.execute(
        service_mechanics.insert().values(ticket_id=ticket.id, mechanic_id=mechanic.id)
    )
    db.session.commit()

    # SQLite enforces the unique constraint immediately on execute(),
    # not deferred until commit() -- so the exception must be expected
    # around the execute() call itself, not the commit() that follows it.
    with pytest.raises(IntegrityError):
        db.session.execute(
            service_mechanics.insert().values(ticket_id=ticket.id, mechanic_id=mechanic.id)
        )
    db.session.rollback()
