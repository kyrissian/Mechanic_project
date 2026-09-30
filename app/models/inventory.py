"""
Inventory model: a part the shop stocks and can use on service tickets.

Not part of the class-provided ERD. price uses Decimal (Numeric) rather
than float, matching ServiceTicket.cost and Mechanic.salary: money
shouldn't live in binary floating point. The assignment text says
"float value" for price; Decimal is a deliberate, documented departure.

quantity_on_hand tracks how many of this part the shop currently has
in stock. It is decremented automatically when a part is added to a
ticket (see add_part_to_ticket in the service_ticket blueprint), and
that route refuses to add more of a part than is currently in stock --
so this number always reflects real, allocatable inventory, not just
a manually-maintained count a manager could forget to update.

A part relates to tickets many-to-many through the TicketPart junction
model (see app/models/ticket_part.py), which also stores quantity and
the price at the time the part was added.
"""

from decimal import Decimal
from typing import List, TYPE_CHECKING

from sqlalchemy import Numeric
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.extensions import db

if TYPE_CHECKING:
    from app.models.ticket_part import TicketPart


class Inventory(db.Model):
    """A part in the shop's catalog, with its current price and how
    many are currently in stock."""

    __tablename__ = "inventory"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(db.String(150), nullable=False, unique=True)
    price: Mapped[Decimal] = mapped_column(Numeric(10, 2), nullable=False)
    quantity_on_hand: Mapped[int] = mapped_column(nullable=False, default=0)

    ticket_parts: Mapped[List["TicketPart"]] = relationship(back_populates="part")
