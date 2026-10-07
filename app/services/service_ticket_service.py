"""
Business logic for the Service Ticket resource. See
app/services/__init__.py for why this layer exists.
"""

from app.extensions import db
from app.models.customer import Customer
from app.models.inventory import Inventory
from app.models.mechanic import Mechanic
from app.models.ticket_part import TicketPart


def customer_is_active(customer_id):
    """A ticket may only be created for a real, still-active
    customer -- returns that Customer, or None."""
    customer = db.session.get(Customer, customer_id)
    if customer and customer.is_active:
        return customer
    return None


def mechanic_is_assigned(ticket, mechanic_id):
    """The rule behind both status updates and add-part: a mechanic
    with no connection to a ticket may not act on it, even though
    both actions are otherwise open to any mechanic in general."""
    mechanic = db.session.get(Mechanic, mechanic_id)
    return mechanic is not None and mechanic in ticket.mechanics


def resolve_mechanics_or_error(mechanic_ids):
    """Look up every id up front, before any change is applied, so a
    single bad id in a bulk add/remove request never leaves the
    ticket half-updated. Returns (mechanics, None) on success, or
    (None, the first missing id) on failure."""
    mechanics = []
    for mechanic_id in mechanic_ids:
        mechanic = db.session.get(Mechanic, mechanic_id)
        if not mechanic:
            return None, mechanic_id
        mechanics.append(mechanic)
    return mechanics, None


def allocate_part(ticket, inventory_id, quantity):
    """Add `quantity` of a part to a ticket. Refuses to allocate more
    than quantity_on_hand, naming exactly how many are available,
    since the alternative -- letting stock go negative -- would make
    the number meaningless. Snapshots the part's CURRENT price onto
    the line, so a later price change never rewrites what this
    ticket already recorded. Mutates but does not commit; the
    caller owns the transaction.

    Returns (error_message_or_None, part).
    """
    part = db.session.get(Inventory, inventory_id)
    if not part:
        return "Part not found.", None

    if quantity > part.quantity_on_hand:
        return (
            f"Not enough {part.name} in stock. "
            f"Requested {quantity}, only {part.quantity_on_hand} available."
        ), part

    line = db.session.get(TicketPart, (ticket.id, inventory_id))
    if line:
        line.quantity += quantity
    else:
        db.session.add(
            TicketPart(
                ticket_id=ticket.id,
                inventory_id=inventory_id,
                quantity=quantity,
                unit_price=part.price,
            )
        )
    part.quantity_on_hand -= quantity
    return None, part
