"""
ServiceTicket model.

id, vin, service_desc, and the customer foreign key match the
lesson's provided ERD. service_date was originally a VARCHAR per that
ERD, matched exactly at first out of caution -- on review, nothing in
the assignment actually requires strict ERD fidelity, so service_date
is now a real Date column: it's an actual calendar date, and storing
it as one enables real date comparison and sorting (e.g. the
oldest-tickets-first triage view), which a string can only fake.

status and cost are NOT part of the class-provided ERD -- added for
the role-based authorization extension of this project, same
documented-departure treatment as Customer.password_hash. status
tracks the ticket through its real-world lifecycle (see the schema's
OneOf validator for the exact five values); cost is the estimate
given up front and may be revised later by a manager. cost uses
db.Numeric (Python's Decimal) rather than a plain float, since binary
floating point cannot represent most decimal currency values exactly
-- the same reasoning now applied to Mechanic.salary as well.

Belongs to exactly one Customer (one-to-many). Related to Mechanic
through the service_mechanics junction table (many-to-many: a ticket
can need multiple mechanics, a mechanic can work multiple tickets).
"""

from datetime import date
from decimal import Decimal
from typing import List, TYPE_CHECKING

from sqlalchemy import ForeignKey, Numeric
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.extensions import db

if TYPE_CHECKING:
    from app.models.customer import Customer
    from app.models.mechanic import Mechanic


class ServiceTicket(db.Model):
    """A record of a single service visit: the vehicle's VIN, the
    date, a description of the work, its current status, and its
    cost, linked to its customer and the mechanic(s) assigned."""

    __tablename__ = "service_tickets"

    id: Mapped[int] = mapped_column(primary_key=True)
    vin: Mapped[str] = mapped_column(db.String(17), nullable=False)
    service_date: Mapped[date] = mapped_column(nullable=False)
    service_desc: Mapped[str] = mapped_column(db.String(500), nullable=False)
    # "Pending" | "In Progress" | "Completed" | "Paid" | "Picked Up".
    # Enforced by ServiceTicketSchema's OneOf validator, not a DB
    # constraint -- same approach as the VIN format, kept at the
    # schema layer rather than the model layer throughout this project.
    status: Mapped[str] = mapped_column(
        db.String(20), nullable=False, default="Pending"
    )
    # Numeric(10, 2): up to 8 digits before the decimal point and
    # exactly 2 after -- comfortably covers any real repair bill
    # while storing it as an exact decimal, not a binary float.
    cost: Mapped[Decimal] = mapped_column(Numeric(10, 2), nullable=False)
    customer_id: Mapped[int] = mapped_column(
        ForeignKey("customers.id"), nullable=False
    )

    customer: Mapped["Customer"] = relationship(back_populates="service_tickets")
    mechanics: Mapped[List["Mechanic"]] = relationship(
        secondary="service_mechanics", back_populates="service_tickets"
    )
