"""
ServiceTicket model.

Fields match the class ERD (Service_Ticket table): date received,
vehicle make/model/year/VIN, work description, and status. Belongs
to exactly one Customer (one-to-many: a customer can have many
tickets). Related to Mechanic through the st_mechanic junction table
(many-to-many: a ticket can need multiple mechanics, a mechanic can
work multiple tickets).
"""

from datetime import date
from typing import List, Optional, TYPE_CHECKING

from sqlalchemy import ForeignKey
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.extensions import db

if TYPE_CHECKING:
    from app.models.customer import Customer
    from app.models.mechanic import Mechanic


class ServiceTicket(db.Model):
    """A record of a single service visit: the vehicle involved, the
    work needed, its status, and who's assigned to it."""

    __tablename__ = "service_tickets"

    id: Mapped[int] = mapped_column(primary_key=True)
    customer_id: Mapped[int] = mapped_column(
        ForeignKey("customers.id"), nullable=False
    )
    date_received: Mapped[date] = mapped_column(nullable=False)
    make: Mapped[str] = mapped_column(db.String(100), nullable=False)
    model: Mapped[str] = mapped_column(db.String(100), nullable=False)
    year: Mapped[int] = mapped_column(nullable=False)
    vin: Mapped[str] = mapped_column(db.String(17), nullable=False)
    work_description: Mapped[Optional[str]] = mapped_column(db.String(500))
    status: Mapped[str] = mapped_column(db.String(50), nullable=False)

    customer: Mapped["Customer"] = relationship(back_populates="service_tickets")
    mechanics: Mapped[List["Mechanic"]] = relationship(
        secondary="st_mechanic", back_populates="service_tickets"
    )