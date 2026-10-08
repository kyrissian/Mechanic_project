"""
Direct unit tests for the service layer (app/services/).

Unlike the route-level tests, these call service functions directly,
with no Flask request, no HTTP client, and no authentication --
exactly the benefit a service layer is supposed to provide: a
business rule can be tested on its own, in isolation, without
standing up a whole fake request to reach it. Every rule here is
also exercised indirectly through the existing route tests; these
tests exist to prove the rule itself is correct at the source,
independent of how a route happens to call it.
"""

from decimal import Decimal

from app.models.customer import Customer
from app.models.inventory import Inventory
from app.models.mechanic import Mechanic
from app.models.service_ticket import ServiceTicket
from app.models.ticket_part import TicketPart
from app.services import (
    customer_service,
    inventory_service,
    mechanic_service,
    service_ticket_service,
)
from tests.conftest import (
    make_customer_kwargs,
    make_mechanic_kwargs,
    make_service_ticket_kwargs,
    seed_customer_mechanic_ticket,
)


# ---- customer_service ----

def test_email_taken_true_for_existing_email(db):
    """email_taken should return True once a customer with that
    email exists."""
    db.session.add(Customer(**make_customer_kwargs()))
    db.session.commit()

    assert customer_service.email_taken("jamie@example.com") is True


def test_email_taken_excludes_own_row_on_update(db):
    """email_taken should return False when exclude_id points at the
    only customer using that email -- otherwise a customer who
    updates their account without changing their email would
    incorrectly conflict with themselves."""
    customer = Customer(**make_customer_kwargs())
    db.session.add(customer)
    db.session.commit()

    assert customer_service.email_taken("jamie@example.com", exclude_id=customer.id) is False


def test_has_service_history_false_for_new_customer(db):
    """A customer with zero tickets should be eligible for
    self-service deletion."""
    customer = Customer(**make_customer_kwargs())
    db.session.add(customer)
    db.session.commit()

    assert customer_service.has_service_history(customer.id) is False


def test_has_service_history_true_once_a_ticket_exists(db):
    """A single ticket, regardless of its status, is enough to block
    self-service deletion -- any service history counts."""
    customer = Customer(**make_customer_kwargs())
    db.session.add(customer)
    db.session.commit()
    db.session.add(ServiceTicket(customer_id=customer.id, **make_service_ticket_kwargs()))
    db.session.commit()

    assert customer_service.has_service_history(customer.id) is True


def test_anonymize_scrubs_identity_and_marks_closed(db):
    """anonymize should replace every identifying field and set
    deleted_at, without deleting the row itself -- a ticket's
    customer_id foreign key must keep pointing at something real."""
    customer = Customer(**make_customer_kwargs())
    db.session.add(customer)
    db.session.commit()
    original_id = customer.id

    customer_service.anonymize(customer)

    assert customer.id == original_id  # same row, not deleted
    assert customer.name == "Deleted Customer"
    assert customer.email == f"deleted-{original_id}@deleted.invalid"
    assert customer.phone == "N/A"
    assert customer.deleted_at is not None
    assert customer.is_active is False


# ---- mechanic_service ----

def test_mechanic_email_taken_true_for_existing_email(db):
    """email_taken should return True once a mechanic with that
    email exists."""
    db.session.add(Mechanic(**make_mechanic_kwargs()))
    db.session.commit()

    assert mechanic_service.email_taken("alex@example.com") is True


def test_mechanic_email_taken_excludes_own_row_on_update(db):
    """Same self-conflict exclusion as the customer version --
    keeping an unchanged email on update is never a conflict."""
    mechanic = Mechanic(**make_mechanic_kwargs())
    db.session.add(mechanic)
    db.session.commit()

    assert mechanic_service.email_taken("alex@example.com", exclude_id=mechanic.id) is False


def test_count_tickets_by_status_counts_only_matching_statuses(db):
    """count_tickets_by_status should count only tickets whose
    status is in the given list, ignoring everything else the
    mechanic is assigned to."""
    customer = Customer(**make_customer_kwargs())
    mechanic = Mechanic(**make_mechanic_kwargs())
    open_ticket = ServiceTicket(
        customer=customer, status="Pending", **make_service_ticket_kwargs(vin="1" * 17)
    )
    closed_ticket = ServiceTicket(
        customer=customer, status="Paid", **make_service_ticket_kwargs(vin="2" * 17)
    )
    open_ticket.mechanics.append(mechanic)
    closed_ticket.mechanics.append(mechanic)
    db.session.add_all([customer, mechanic, open_ticket, closed_ticket])
    db.session.commit()

    open_count = mechanic_service.count_tickets_by_status(mechanic, ["Pending", "In Progress"])
    closed_count = mechanic_service.count_tickets_by_status(mechanic, ["Paid", "Picked Up"])

    assert open_count == 1
    assert closed_count == 1


def test_mechanic_summary_excludes_salary(db):
    """mechanic_summary should expose id/name plus whatever extra
    fields are passed, but never salary -- the sorting endpoints that
    use this are open to any mechanic, not just managers."""
    mechanic = Mechanic(**make_mechanic_kwargs())
    db.session.add(mechanic)
    db.session.commit()

    summary = mechanic_service.mechanic_summary(mechanic, ticket_count=3)

    assert summary == {"id": mechanic.id, "name": "Alex Chen", "ticket_count": 3}
    assert "salary" not in summary


# ---- service_ticket_service ----

def test_customer_is_active_for_a_real_active_customer(db):
    """customer_is_active should return the Customer object itself
    when the account exists and hasn't been closed."""
    customer = Customer(**make_customer_kwargs())
    db.session.add(customer)
    db.session.commit()

    result = service_ticket_service.customer_is_active(customer.id)

    assert result is not None
    assert result.id == customer.id


def test_customer_is_active_none_for_closed_account(db):
    """A closed (soft-deleted) customer should not be usable for a
    new ticket, even though the row still exists."""
    customer = Customer(**make_customer_kwargs())
    db.session.add(customer)
    db.session.commit()
    customer_service.anonymize(customer)
    db.session.commit()

    assert service_ticket_service.customer_is_active(customer.id) is None


def test_customer_is_active_none_for_nonexistent_id(db):  # pylint: disable=unused-argument
    """A customer id that doesn't exist at all should also be None,
    not an error."""
    assert service_ticket_service.customer_is_active(999999) is None


def test_mechanic_is_assigned_true_when_on_the_ticket(db):
    """mechanic_is_assigned should return True once the mechanic is
    in the ticket's own mechanics list."""
    customer = Customer(**make_customer_kwargs())
    mechanic = Mechanic(**make_mechanic_kwargs())
    ticket = ServiceTicket(customer=customer, **make_service_ticket_kwargs())
    ticket.mechanics.append(mechanic)
    db.session.add_all([customer, mechanic, ticket])
    db.session.commit()

    assert service_ticket_service.mechanic_is_assigned(ticket, mechanic.id) is True


def test_mechanic_is_assigned_false_when_not_on_the_ticket(db):
    """A mechanic with no connection to a ticket should not be
    treated as assigned to it."""
    _, mechanic, ticket = seed_customer_mechanic_ticket(db)

    assert service_ticket_service.mechanic_is_assigned(ticket, mechanic.id) is False


def test_resolve_mechanics_or_error_returns_all_on_success(db):
    """Given valid ids, resolve_mechanics_or_error should return the
    full list of Mechanic objects and no missing id."""
    mechanic_a = Mechanic(**make_mechanic_kwargs(email="a@example.com"))
    mechanic_b = Mechanic(**make_mechanic_kwargs(email="b@example.com"))
    db.session.add_all([mechanic_a, mechanic_b])
    db.session.commit()

    mechanics, missing_id = service_ticket_service.resolve_mechanics_or_error(
        [mechanic_a.id, mechanic_b.id]
    )

    assert missing_id is None
    assert len(mechanics) == 2


def test_resolve_mechanics_or_error_stops_at_first_missing_id(db):  # pylint: disable=unused-argument
    """A nonexistent id anywhere in the list should short-circuit
    with that id, before any change is made -- so a bulk edit never
    leaves a ticket half-updated on a bad id."""
    mechanics, missing_id = service_ticket_service.resolve_mechanics_or_error([999999])

    assert mechanics is None
    assert missing_id == 999999


def test_allocate_part_decrements_stock_and_snapshots_price(db):
    """A successful allocation should create a TicketPart line at the
    part's CURRENT price, and reduce quantity_on_hand by exactly the
    amount allocated."""
    customer = Customer(**make_customer_kwargs())
    ticket = ServiceTicket(customer=customer, **make_service_ticket_kwargs())
    part = Inventory(name="Oil Filter", price=Decimal("12.50"), quantity_on_hand=20)
    db.session.add_all([customer, ticket, part])
    db.session.commit()

    error, _ = service_ticket_service.allocate_part(ticket, part.id, 2)
    db.session.commit()

    assert error is None
    assert part.quantity_on_hand == 18
    line = db.session.get(TicketPart, (ticket.id, part.id))
    assert line.quantity == 2
    assert line.unit_price == Decimal("12.50")


def test_allocate_part_refuses_to_exceed_stock(db):
    """Requesting more than quantity_on_hand should be refused with a
    message naming exactly how many are available, and must leave
    stock completely unchanged."""
    customer = Customer(**make_customer_kwargs())
    ticket = ServiceTicket(customer=customer, **make_service_ticket_kwargs())
    part = Inventory(name="Brake Rotor", price=Decimal("74.50"), quantity_on_hand=3)
    db.session.add_all([customer, ticket, part])
    db.session.commit()

    error, _ = service_ticket_service.allocate_part(ticket, part.id, 5)

    assert error == "Not enough Brake Rotor in stock. Requested 5, only 3 available."
    assert part.quantity_on_hand == 3  # unchanged


def test_allocate_part_adds_to_existing_line_on_repeat(db):
    """Allocating the same part to the same ticket twice should
    increase the existing line's quantity, not create a second one."""
    customer = Customer(**make_customer_kwargs())
    ticket = ServiceTicket(customer=customer, **make_service_ticket_kwargs())
    part = Inventory(name="Oil Filter", price=Decimal("12.50"), quantity_on_hand=20)
    db.session.add_all([customer, ticket, part])
    db.session.commit()

    service_ticket_service.allocate_part(ticket, part.id, 1)
    db.session.commit()
    service_ticket_service.allocate_part(ticket, part.id, 2)
    db.session.commit()

    line = db.session.get(TicketPart, (ticket.id, part.id))
    assert line.quantity == 3
    assert part.quantity_on_hand == 17


# ---- inventory_service ----

def test_name_taken_is_case_insensitive(db):
    """A part named "Oil Filter" should block "oil filter" too --
    names are compared case-insensitively."""
    db.session.add(Inventory(name="Oil Filter", price=Decimal("12.50"), quantity_on_hand=20))
    db.session.commit()

    assert inventory_service.name_taken("oil filter") is True


def test_name_taken_excludes_own_row_on_update(db):
    """Keeping a part's own existing name during an update should
    never be flagged as a conflict with itself."""
    part = Inventory(name="Oil Filter", price=Decimal("12.50"), quantity_on_hand=20)
    db.session.add(part)
    db.session.commit()

    assert inventory_service.name_taken("Oil Filter", exclude_id=part.id) is False


def test_has_been_used_true_once_on_a_ticket(db):
    """A part with even one TicketPart line counts as used, and
    should therefore be blocked from deletion."""
    customer = Customer(**make_customer_kwargs())
    ticket = ServiceTicket(customer=customer, **make_service_ticket_kwargs())
    part = Inventory(name="Oil Filter", price=Decimal("12.50"), quantity_on_hand=20)
    line = TicketPart(ticket=ticket, part=part, quantity=1, unit_price=Decimal("12.50"))
    db.session.add_all([customer, ticket, part, line])
    db.session.commit()

    assert inventory_service.has_been_used(part) is True


def test_has_been_used_false_for_an_unused_part(db):
    """A part that's never been added to any ticket should be
    deletable."""
    part = Inventory(name="Oil Filter", price=Decimal("12.50"), quantity_on_hand=20)
    db.session.add(part)
    db.session.commit()

    assert inventory_service.has_been_used(part) is False
