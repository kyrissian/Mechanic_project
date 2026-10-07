"""
Business logic for the Inventory resource. See
app/services/__init__.py for why this layer exists.
"""

from sqlalchemy import select

from app.extensions import db
from app.models.inventory import Inventory


def name_taken(name, exclude_id=None):
    """Compared case-insensitively, so "Oil Filter" and "oil filter"
    can't both exist. exclude_id lets an update keep its own name."""
    query = select(Inventory).where(db.func.lower(Inventory.name) == name.lower())
    if exclude_id is not None:
        query = query.where(Inventory.id != exclude_id)
    return db.session.execute(query).scalars().first() is not None


def has_been_used(part):
    """A part on even one ticket can't be deleted -- the same
    "history stays" principle applied to customer accounts and
    tickets themselves. Renaming or repricing a used part is still
    always allowed; only deletion is blocked."""
    return bool(part.ticket_parts)
