"""
Mechanic model.

id, name, email, phone match the lesson's provided ERD. salary was
originally FLOAT per that ERD, matched exactly at first out of
caution -- on review, nothing in the assignment actually requires
strict ERD fidelity (it only specifies the required fields and
routes), so salary now uses the same textbook-correct Decimal as
ServiceTicket.cost, rather than binary floating point for money.

The many-to-many relationship to ServiceTicket -- per the ERD's own
annotation: "One ticket might require multiple mechanics, and a
single mechanic will work on multiple tickets" -- is implemented
through the service_mechanics junction table (see
app/models/service_mechanics.py).

password_hash and role are NOT part of the class-provided ERD --
added for the role-based authorization extension of this project,
same documented-departure treatment as Customer.password_hash: every
mechanic account now needs to log in, and needs a role to distinguish
regular mechanics from managers.
"""

from decimal import Decimal
from typing import List, TYPE_CHECKING

from sqlalchemy import Numeric
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.extensions import db

if TYPE_CHECKING:
    from app.models.service_ticket import ServiceTicket


class Mechanic(db.Model):
    """A shop mechanic, who can be assigned to work on one or more
    service tickets. role is either "mechanic" or "manager" --
    managers can edit ticket descriptions/cost and assign mechanics;
    any mechanic (including managers) can update a ticket's status.
    """

    __tablename__ = "mechanics"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(db.String(100), nullable=False)
    email: Mapped[str] = mapped_column(db.String(255), nullable=False, unique=True)
    phone: Mapped[str] = mapped_column(db.String(20), nullable=False)
    # Numeric(10, 2): exact decimal storage, same as ServiceTicket.cost
    # -- avoids binary-float rounding error for a currency value.
    salary: Mapped[Decimal] = mapped_column(Numeric(10, 2), nullable=False)
    # Never stores a plaintext password. Routes hash it with
    # werkzeug.security.generate_password_hash before this is ever
    # set, and verify with check_password_hash on login -- same
    # pattern as Customer.password_hash.
    password_hash: Mapped[str] = mapped_column(db.String(255), nullable=False)
    role: Mapped[str] = mapped_column(db.String(20), nullable=False)

    service_tickets: Mapped[List["ServiceTicket"]] = relationship(
        secondary="service_mechanics", back_populates="mechanics"
    )
