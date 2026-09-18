"""
Marshmallow schema for the ServiceTicket model.
"""

from app.extensions import ma
from app.models.service_ticket import ServiceTicket


class ServiceTicketSchema(ma.SQLAlchemyAutoSchema):
    """Auto-generates fields from the ServiceTicket model's columns."""

    class Meta:
        """Points the schema at the ServiceTicket model to derive fields from.

        include_fk = True is required here specifically: SQLAlchemyAutoSchema
        excludes foreign key columns by default, but customer_id is exactly
        the field a client needs to send when creating a ticket -- without
        this, customer_id would be silently missing from the schema
        entirely, and every ticket creation would fail.
        """

        model = ServiceTicket
        load_instance = False
        include_fk = True

    id = ma.auto_field(dump_only=True)

    # SQLAlchemyAutoSchema only generates fields from plain columns,
    # not relationship() attributes -- without this, the assign/remove
    # -mechanic routes would work correctly against the database, but
    # a ticket's response would never show which mechanics are
    # actually assigned to it, making a successful assignment
    # indistinguishable from a silent no-op at the API level.
    mechanic_ids = ma.Method("get_mechanic_ids", dump_only=True)

    def get_mechanic_ids(self, obj):
        """Returns the ids of every mechanic currently assigned to
        this ticket, read directly from the relationship."""
        return [mechanic.id for mechanic in obj.mechanics]


service_ticket_schema = ServiceTicketSchema()
service_tickets_schema = ServiceTicketSchema(many=True)
