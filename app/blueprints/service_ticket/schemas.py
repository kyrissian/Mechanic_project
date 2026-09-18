"""
Marshmallow schema for the ServiceTicket model.
"""

from marshmallow import validate

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

    # The model's db.String(17) column gives us a maximum-length
    # validator automatically, but only a maximum -- a 1-character
    # string was still accepted as a valid VIN. A real VIN is always
    # exactly 17 characters (Length), and per ISO 3779 never contains
    # the letters I, O, or Q -- they're deliberately excluded from the
    # standard because they're too easily confused with 1, 0, and 9
    # (Regexp). Both explicitly override the auto-derived field.
    vin = ma.auto_field(
        validate=[
            validate.Length(equal=17),
            validate.Regexp(
                r"^[A-HJ-NPR-Z0-9]+$",
                error="VIN may only contain uppercase letters and digits, excluding I, O, and Q.",
            ),
        ]
    )

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
