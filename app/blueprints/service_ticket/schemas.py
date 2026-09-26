"""
Marshmallow schema for the ServiceTicket model.
"""

from marshmallow import fields, validate

from app.extensions import ma
from app.models.service_ticket import ServiceTicket

# Single source of truth for the valid status values, shared by the
# schema's OneOf validator below and the open/closed split used by
# the ticket-counting sort endpoints, so the two can never drift
# apart.
VALID_STATUSES = ["Pending", "In Progress", "Completed", "Paid", "Picked Up"]
OPEN_STATUSES = ["Pending", "In Progress", "Completed"]
CLOSED_STATUSES = ["Paid", "Picked Up"]


class ServiceTicketSchema(ma.SQLAlchemyAutoSchema):
    """Auto-generates fields from the ServiceTicket model's columns.

    include_fk = True is required here specifically: SQLAlchemyAutoSchema
    excludes foreign key columns by default, but customer_id is exactly
    the field a client needs to send when creating a ticket -- without
    this, customer_id would be silently missing from the schema
    entirely, and every ticket creation would fail.
    """

    class Meta:
        """Points the schema at the ServiceTicket model to derive fields from."""

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

    # Restricted to the five real-world stages a ticket moves through.
    # Not required on input: defaults to "Pending" at the model level
    # for a brand-new ticket. Changed afterward only via the dedicated
    # status-update route, not this schema's own PUT usage.
    status = fields.String(
        required=False, validate=validate.OneOf(VALID_STATUSES)
    )

    # cost is Numeric(10, 2) in the model (see service_ticket.py) --
    # as_string=True makes Marshmallow serialize it as a JSON string
    # (e.g. "450.00") rather than trying to serialize a raw Decimal,
    # which Flask's default JSON encoder can't do at all. It still
    # accepts an int, float, or string on input. Required: an
    # estimate must be given up front when a ticket is created.
    cost = fields.Decimal(as_string=True, places=2, required=True)

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


class TicketDetailsUpdateSchema(ma.Schema):
    """For PUT /service-tickets/<id> (manager-only): a partial update
    of just the ticket's description and/or cost. Not tied to the
    model via SQLAlchemyAutoSchema, since this route deliberately
    accepts a subset of fields rather than a full replacement -- both
    fields are optional, but the route itself requires at least one
    to be present (an empty edit is rejected there, not here).
    """

    service_desc = fields.String(required=False)
    cost = fields.Decimal(as_string=True, places=2, required=False)


class StatusUpdateSchema(ma.Schema):
    """For PUT /service-tickets/<id>/status (any mechanic): the one
    field this route is allowed to change."""

    status = fields.String(required=True, validate=validate.OneOf(VALID_STATUSES))


class TicketMechanicEditSchema(ma.Schema):
    """For PUT /service-tickets/<id>/edit (manager-only, bulk):
    lists of mechanic ids to add and/or remove in one request. Both
    default to an empty list, so a caller only needs to send the one
    they actually want to use.
    """

    add_ids = fields.List(fields.Integer(), load_default=list)
    remove_ids = fields.List(fields.Integer(), load_default=list)


service_ticket_schema = ServiceTicketSchema()
service_tickets_schema = ServiceTicketSchema(many=True)
ticket_details_update_schema = TicketDetailsUpdateSchema()
status_update_schema = StatusUpdateSchema()
ticket_mechanic_edit_schema = TicketMechanicEditSchema()
