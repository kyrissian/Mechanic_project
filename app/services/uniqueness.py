"""
Shared "is this value already taken" check.

Before this module existed, customer_service.email_taken and
mechanic_service.email_taken were two copies of the identical
query shape (select the model, filter by one column, optionally
exclude a row by id, return whether anything matched); and
inventory_service.name_taken was the same shape again, with a
case-insensitive comparison. This factors that one query pattern
into a single place, so a change to how uniqueness is checked (e.g.
trimming whitespace before comparing) only has to happen once.
"""

from sqlalchemy import select

from app.extensions import db


def value_taken(model, column, value, exclude_id=None, case_insensitive=False):
    """True if some OTHER row of `model` already has `value` in
    `column`.

    `exclude_id` lets an update ignore the record's own current row,
    so keeping an unchanged value is never flagged as a conflict
    with itself. `case_insensitive` compares via SQL lower() on both
    sides, for fields like a part name where "Oil Filter" and
    "oil filter" should count as the same value.
    """
    if case_insensitive:
        query = select(model).where(db.func.lower(column) == value.lower())
    else:
        query = select(model).where(column == value)

    if exclude_id is not None:
        query = query.where(model.id != exclude_id)

    return db.session.execute(query).scalars().first() is not None
