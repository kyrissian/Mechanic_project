"""
Mechanic model.

Fields match the lesson's provided ERD (mechanics table): id, name,
email, phone, salary (FLOAT). The many-to-many relationship to
ServiceTicket -- per the ERD's own annotation: "One ticket might
require multiple mechanics, and a single mechanic will work on
multiple tickets" -- is implemented through the service_mechanics
junction table (see app/models/service_mechanics.py).
"""

from typing import List, TYPE_CHECKING

from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.extensions import db

if TYPE_CHECKING:
    from app.models.service_ticket import ServiceTicket


class Mechanic(db.Model):
    """A shop mechanic, who can be assigned to work on one or more
    service tickets."""

    __tablename__ = "mechanics"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(db.String(100), nullable=False)
    email: Mapped[str] = mapped_column(db.String(255), nullable=False, unique=True)
    phone: Mapped[str] = mapped_column(db.String(20), nullable=False)
    salary: Mapped[float] = mapped_column(nullable=False)

    service_tickets: Mapped[List["ServiceTicket"]] = relationship(
        secondary="service_mechanics", back_populates="mechanics"
    )
