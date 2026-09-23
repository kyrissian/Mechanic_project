"""
Marshmallow schema for the Customer model.

Lives alongside routes.py in this blueprint's own folder (rather than
in a project-wide schemas/ folder) -- each resource's routes and its
schema are kept together, since they're only ever used together.

Used for three jobs at once: validating incoming JSON on create/update
(does it have the right fields, right types?), deserializing that
JSON into a plain dict of Python values, and serializing a Customer
object back into JSON for responses.
"""

from marshmallow import fields

from app.extensions import ma
from app.models.customer import Customer


class CustomerSchema(ma.SQLAlchemyAutoSchema):
    """Auto-generates fields from the Customer model's columns."""

    class Meta:
        """Points the schema at the Customer model to derive fields from.

        password_hash is excluded entirely -- it must never be
        accepted directly from a client (routes hash the plaintext
        `password` field below themselves) or appear in a serialized
        response.
        """

        model = Customer
        load_instance = False
        exclude = ("password_hash",)

    # Explicitly dump_only rather than relying on SQLAlchemyAutoSchema's
    # default behavior for primary keys -- this guarantees `id` can
    # never be required or accepted on create/update (it's server
    # generated), while still appearing in serialized responses.
    id = ma.auto_field(dump_only=True)

    # Not a real model column -- this is the plaintext password a
    # client sends on create/update. Routes hash it with
    # generate_password_hash before constructing/updating a Customer.
    # load_only guarantees it can never be echoed back in a response,
    # even by accident.
    password = fields.String(required=True, load_only=True)


class LoginSchema(ma.SQLAlchemyAutoSchema):
    """Accepts only email and password, for POST /customers/login."""

    class Meta:
        """Restricted to just the two fields a login attempt needs."""

        model = Customer
        load_instance = False
        fields = ("email", "password")

    # Same reasoning as CustomerSchema.password above.
    password = fields.String(required=True, load_only=True)


customer_schema = CustomerSchema()
customers_schema = CustomerSchema(many=True)
login_schema = LoginSchema()
