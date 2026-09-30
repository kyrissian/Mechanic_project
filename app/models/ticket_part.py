"""
TicketPart model: the junction between ServiceTicket and Inventory.

The assignment allows a bare db.Table here, but offers a modeled
junction with a quantity as an optional challenge. This is that
version, since a ticket can use several of the same part.

The primary key is the (ticket_id, inventory_id) pair, so a part can
appear only once per ticket; adding it again increases quantity
instead of creating a second row.

unit_price is copied from Inventory.price when the part is first
added. Without it, editing a part's price later would silently
change what every past ticket appears to have cost.
"""

from decimal import Decimal
from typing import TYPE_CHECKING

from sqlalchemy import ForeignKey, Numeric
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.extensions import db

if TYPE_CHECKING:
    from app.models.inventory import Inventory
    from app.models.service_ticket import ServiceTicket


class TicketPart(db.Model):
    """One line on a ticket: a part, how many, and the price per unit
    at the time it was added."""

    __tablename__ = "ticket_parts"

    ticket_id: Mapped[int] = mapped_column(
        ForeignKey("service_tickets.id"), primary_key=True, autoincrement=False
    )
    inventory_id: Mapped[int] = mapped_column(
        ForeignKey("inventory.id"), primary_key=True, autoincrement=False
    )
    quantity: Mapped[int] = mapped_column(nullable=False, default=1)
    unit_price: Mapped[Decimal] = mapped_column(Numeric(10, 2), nullable=False)

    ticket: Mapped["ServiceTicket"] = relationship(back_populates="ticket_parts")
    part: Mapped["Inventory"] = relationship(back_populates="ticket_parts")
