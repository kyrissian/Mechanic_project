"""
Business logic for the Mechanic resource. See app/services/__init__.py
for why this layer exists.
"""

from sqlalchemy import select

from app.extensions import db
from app.models.mechanic import Mechanic


def email_taken(email, exclude_id=None):
    """When updating a mechanic, the duplicate-email check must
    ignore that mechanic's own current row -- otherwise keeping an
    unchanged email would look like a conflict with itself."""
    query = select(Mechanic).where(Mechanic.email == email)
    if exclude_id is not None:
        query = query.where(Mechanic.id != exclude_id)
    return db.session.execute(query).scalars().first() is not None


def count_tickets_by_status(mechanic, statuses):
    """Shared by the open/closed sorting endpoints, so both read the
    same single source of truth for what counts as open vs. closed."""
    return len([t for t in mechanic.service_tickets if t.status in statuses])


def mechanic_summary(mechanic, **extra_fields):
    """id and name only -- deliberately excludes salary, since the
    sorting endpoints are open to any mechanic and sorting by
    workload doesn't require seeing anyone's pay."""
    return {"id": mechanic.id, "name": mechanic.name, **extra_fields}
