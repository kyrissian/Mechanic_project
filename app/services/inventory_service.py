"""
Business logic for the Inventory resource. See
app/services/__init__.py for why this layer exists.
"""

from app.models.inventory import Inventory
from app.services.uniqueness import value_taken


def name_taken(name, exclude_id=None):
    """Compared case-insensitively, so "Oil Filter" and "oil filter"
    can't both exist. exclude_id lets an update keep its own name."""
    return value_taken(
        Inventory, Inventory.name, name, exclude_id=exclude_id, case_insensitive=True
    )


def has_been_used(part):
    """A part on even one ticket can't be deleted -- the same
    "history stays" principle applied to customer accounts and
    tickets themselves. Renaming or repricing a used part is still
    always allowed; only deletion is blocked."""
    return bool(part.ticket_parts)
