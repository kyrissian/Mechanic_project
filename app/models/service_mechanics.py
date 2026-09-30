"""
Junction table for the many-to-many relationship between
ServiceTicket and Mechanic (one ticket can need multiple mechanics,
one mechanic can work on multiple tickets).

Named and structured to match the lesson's provided ERD: table name
service_mechanics, columns ticket_id and mechanic_id (not
st_mechanic/st_id/mech_id, which was our own earlier naming before
this ERD was provided).

Unlike the lesson's own loan_book example, the two columns here ARE
marked as a composite primary key. Duplicate-assignment protection
currently lives at the application level (assign_mechanic in the
service_ticket blueprint checks "if mechanic in ticket.mechanics"
before appending) -- but two near-simultaneous requests could both
pass that check before either commits, producing two rows for the
same (ticket_id, mechanic_id) pair. A composite primary key makes the
database itself refuse the second insert, closing that race
regardless of what the application layer does or doesn't catch. This
mirrors the ERD-fidelity correction already made elsewhere in this
project (see the README's Architecture Notes): nothing in the
assignment actually requires matching the lesson's example exactly on
this point, so the more defensible schema is used instead.
"""

from app.extensions import db

service_mechanics = db.Table(
    "service_mechanics",
    db.metadata,
    db.Column("ticket_id", db.ForeignKey("service_tickets.id"), primary_key=True),
    db.Column("mechanic_id", db.ForeignKey("mechanics.id"), primary_key=True),
)
