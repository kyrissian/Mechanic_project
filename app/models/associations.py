"""
Junction table for the many-to-many relationship between
ServiceTicket and Mechanic (one ticket can need multiple mechanics,
one mechanic can work on multiple tickets).

This mirrors the ERD's ST_Mechanic table. Both columns are marked as
part of a composite primary key -- unlike the lesson's loan_book
example, which leaves its columns unmarked -- specifically so the
database itself rejects the same mechanic being assigned to the same
ticket twice, rather than relying on the app code to prevent that.
"""

from app.extensions import db

st_mechanic = db.Table(
    "st_mechanic",
    db.metadata,
    db.Column("st_id", db.ForeignKey("service_tickets.id"), primary_key=True),
    db.Column("mech_id", db.ForeignKey("mechanics.id"), primary_key=True),
)