"""
Mechanic model.

Fields match the class ERD (Mechanics table): name, phone, address,
salary. The many-to-many relationship to ServiceTicket (a mechanic
can work on many tickets, a ticket can have multiple mechanics) is
implemented through the st_mechanic junction table -- see
app/models/associations.py.
"""

from typing import List, TYPE_CHECKING

from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.extensions import db

if TYPE_CHECKING:
    # Only imported for type hints, not at runtime -- avoids a
    # circular import with service_ticket.py, which imports Mechanic
    # the same way.
    from app.models.service_ticket import ServiceTicket


class Mechanic(db.Model):
    """A shop mechanic, who can be assigned to work on one or more
    service tickets."""

    __tablename__ = "mechanics"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(db.String(100), nullable=False)
    phone: Mapped[str] = mapped_column(db.String(20), nullable=False)
    address: Mapped[str] = mapped_column(db.String(255), nullable=False)
    salary: Mapped[int] = mapped_column(nullable=False)

    service_tickets: Mapped[List["ServiceTicket"]] = relationship(
        secondary="st_mechanic", back_populates="mechanics"
    )