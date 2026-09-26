"""
Marshmallow schema for the Mechanic model.
"""

from marshmallow import fields, validate

from app.extensions import ma
from app.models.mechanic import Mechanic

# Single source of truth for the valid role values, shared by the
# schema's OneOf validator below and anywhere else in the mechanic
# blueprint that needs to check a role (e.g. the manager_required
# decorator) -- avoids the two ever drifting out of sync.
VALID_ROLES = ["mechanic", "manager"]


class MechanicSchema(ma.SQLAlchemyAutoSchema):
    """Auto-generates fields from the Mechanic model's columns.

    password_hash is excluded entirely -- it must never be accepted
    directly from a client or appear in a serialized response, same
    reasoning as CustomerSchema.
    """

    class Meta:
        """Points the schema at the Mechanic model to derive fields from."""

        model = Mechanic
        load_instance = False
        exclude = ("password_hash",)

    id = ma.auto_field(dump_only=True)

    # salary is Numeric(10, 2) in the model (see mechanic.py) --
    # as_string=True makes Marshmallow serialize it as a JSON string
    # (e.g. "55000.00") rather than trying to serialize a raw Decimal,
    # which Flask's default JSON encoder can't do at all. It still
    # accepts an int, float, or string on input.
    salary = fields.Decimal(as_string=True, places=2, required=True)

    # Not a real model column -- this is the plaintext password a
    # client sends on create/update. Routes hash it with
    # generate_password_hash before constructing/updating a Mechanic.
    # load_only guarantees it can never be echoed back in a response,
    # even by accident.
    password = fields.String(required=True, load_only=True)

    # Restricted to the two roles this system recognizes. No default:
    # every mechanic account must be created with an explicit role by
    # the manager creating it (see create_mechanic).
    role = fields.String(required=True, validate=validate.OneOf(VALID_ROLES))


class LoginSchema(ma.SQLAlchemyAutoSchema):
    """Accepts only email and password, for POST /mechanics/login."""

    class Meta:
        """Restricted to just the two fields a login attempt needs."""

        model = Mechanic
        load_instance = False
        fields = ("email", "password")

    # Same reasoning as MechanicSchema.password above.
    password = fields.String(required=True, load_only=True)


mechanic_schema = MechanicSchema()
mechanics_schema = MechanicSchema(many=True)
login_schema = LoginSchema()
