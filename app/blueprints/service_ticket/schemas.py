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


service_ticket_schema = ServiceTicketSchema()
service_tickets_schema = ServiceTicketSchema(many=True)
