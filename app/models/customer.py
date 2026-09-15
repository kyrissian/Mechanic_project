"""
Customer model.

Fields match the lesson's provided ERD (customers table): id, name,
email, phone. Has a one-to-many relationship to ServiceTicket (a
customer can have many service tickets, each ticket belongs to
exactly one customer) -- per the ERD's own annotation: "One customer
should be able to get serviced multiple times."
"""

from typing import List, TYPE_CHECKING

from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.extensions import db

if TYPE_CHECKING:
    from app.models.service_ticket import ServiceTicket


class Customer(db.Model):
    """A customer of the shop, and the owner of any service tickets
    filed under their account."""

    __tablename__ = "customers"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(db.String(100), nullable=False)
    email: Mapped[str] = mapped_column(db.String(255), nullable=False, unique=True)
    phone: Mapped[str] = mapped_column(db.String(20), nullable=False)

    service_tickets: Mapped[List["ServiceTicket"]] = relationship(
        back_populates="customer"
    )
