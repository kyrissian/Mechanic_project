"""
Customer model.

Fields match the lesson's provided ERD (customers table): id, name,
email, phone. Has a one-to-many relationship to ServiceTicket (a
customer can have many service tickets, each ticket belongs to
exactly one customer) -- per the ERD's own annotation: "One customer
should be able to get serviced multiple times."

password_hash is NOT part of the class-provided ERD -- it's added
here specifically for the Token Authentication lesson, which requires
customers to be able to log in. deleted_at is also not in the ERD.

Customers are never hard-deleted. Closing an account sets deleted_at
and scrubs the identifying fields (see delete_customer), but the row
stays, because a customer's tickets are the shop's business records
and must keep pointing at something. is_active is the one place that
decides whether an account is still usable.
"""

from datetime import datetime
from typing import List, Optional, TYPE_CHECKING

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
    # Never stores a plaintext password. Routes hash it with
    # werkzeug.security.generate_password_hash before this is ever
    # set, and verify with check_password_hash on login.
    password_hash: Mapped[str] = mapped_column(db.String(255), nullable=False)
    # NULL for an active account; set (naive UTC) when it is closed.
    deleted_at: Mapped[Optional[datetime]] = mapped_column(nullable=True)

    service_tickets: Mapped[List["ServiceTicket"]] = relationship(
        back_populates="customer"
    )

    @property
    def is_active(self) -> bool:
        """True while the account has not been closed."""
        return self.deleted_at is None
