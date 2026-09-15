"""
Marshmallow schema for the Customer model.

Used for three jobs at once: validating incoming JSON on create/update
(does it have the right fields, right types?), deserializing that
JSON into a plain dict of Python values, and serializing a Customer
object back into JSON for responses.
"""

from app.extensions import ma
from app.models.customer import Customer


class CustomerSchema(ma.SQLAlchemyAutoSchema):
    """Auto-generates fields from the Customer model's columns."""

    class Meta:
        """Points the schema at the Customer model to derive fields from."""

        model = Customer
        load_instance = False

    # Explicitly dump_only rather than relying on SQLAlchemyAutoSchema's
    # default behavior for primary keys -- this guarantees `id` can
    # never be required or accepted on create/update (it's server
    # generated), while still appearing in serialized responses.
    id = ma.auto_field(dump_only=True)


customer_schema = CustomerSchema()
customers_schema = CustomerSchema(many=True)
