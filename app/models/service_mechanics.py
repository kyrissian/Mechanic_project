"""
Junction table for the many-to-many relationship between
ServiceTicket and Mechanic (one ticket can need multiple mechanics,
one mechanic can work on multiple tickets).

Named and structured to match the lesson's provided ERD exactly:
table name service_mechanics, columns ticket_id and mechanic_id (not
st_mechanic/st_id/mech_id, which was our own earlier naming before
this ERD was provided). Matches the lesson's own loan_book example in
not marking either column as a primary key.
"""

from app.extensions import db

service_mechanics = db.Table(
    "service_mechanics",
    db.metadata,
    db.Column("ticket_id", db.ForeignKey("service_tickets.id")),
    db.Column("mechanic_id", db.ForeignKey("mechanics.id")),
)
