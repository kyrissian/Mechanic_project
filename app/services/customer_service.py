"""
Business logic for the Customer resource. See app/services/__init__.py
for why this layer exists.
"""

import secrets
from datetime import datetime, timezone

from sqlalchemy import select
from werkzeug.security import generate_password_hash

from app.extensions import db
from app.models.customer import Customer
from app.models.service_ticket import ServiceTicket


def email_taken(email, exclude_id=None):
    """exclude_id lets an update ignore the customer's own row, so
    keeping an unchanged email is never flagged as a conflict."""
    query = select(Customer).where(Customer.email == email)
    if exclude_id is not None:
        query = query.where(Customer.id != exclude_id)
    return db.session.execute(query).scalars().first() is not None


def has_service_history(customer_id):
    """A customer with any ticket, ever, may not close their own
    account online -- tickets are the shop's business records, and
    letting a customer scrub the identity attached to them would
    defeat that purpose. Only an account with zero tickets qualifies
    for self-service deletion."""
    return db.session.execute(
        select(ServiceTicket.id).where(ServiceTicket.customer_id == customer_id).limit(1)
    ).first() is not None


def anonymize(customer):
    """Scrub identifying fields and mark the account closed, without
    deleting the row -- a ticket's customer_id foreign key must keep
    pointing at something real. The placeholder email uses the
    reserved .invalid domain (never receives mail, never collides)
    and frees the real email for reuse."""
    customer.name = "Deleted Customer"
    customer.email = f"deleted-{customer.id}@deleted.invalid"
    customer.phone = "N/A"
    customer.password_hash = generate_password_hash(secrets.token_urlsafe(32))
    customer.deleted_at = datetime.now(timezone.utc).replace(tzinfo=None)
