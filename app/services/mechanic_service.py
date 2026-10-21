"""
Business logic for the Mechanic resource. See app/services/__init__.py
for why this layer exists.
"""

from sqlalchemy import select

from app.extensions import db
from app.models.mechanic import Mechanic
from app.services.uniqueness import value_taken


def email_taken(email, exclude_id=None):
    """When updating a mechanic, the duplicate-email check must
    ignore that mechanic's own current row -- otherwise keeping an
    unchanged email would look like a conflict with itself."""
    return value_taken(Mechanic, Mechanic.email, email, exclude_id=exclude_id)


def count_tickets_by_status(mechanic, statuses):
    """Shared by the open/closed sorting endpoints, so both read the
    same single source of truth for what counts as open vs. closed."""
    return len([t for t in mechanic.service_tickets if t.status in statuses])


def mechanic_summary(mechanic, **extra_fields):
    """id and name only -- deliberately excludes salary, since the
    sorting endpoints are open to any mechanic and sorting by
    workload doesn't require seeing anyone's pay."""
    return {"id": mechanic.id, "name": mechanic.name, **extra_fields}


def sorted_mechanic_summaries(order, metric_fn, metric_field_name):
    """Builds the response payload for all ticket-count sorting
    endpoints from one shared implementation, so changes to ordering
    behavior or response shape stay consistent across all three."""
    mechanics = list(db.session.execute(select(Mechanic)).scalars().all())
    with_metrics = [(mechanic, metric_fn(mechanic)) for mechanic in mechanics]
    with_metrics.sort(key=lambda pair: pair[1], reverse=order != "asc")
    return [
        mechanic_summary(mechanic, **{metric_field_name: metric})
        for mechanic, metric in with_metrics
    ]
