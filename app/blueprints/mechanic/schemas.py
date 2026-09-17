"""
Marshmallow schema for the Mechanic model.
"""

from app.extensions import ma
from app.models.mechanic import Mechanic


class MechanicSchema(ma.SQLAlchemyAutoSchema):
    """Auto-generates fields from the Mechanic model's columns."""

    class Meta:
        """Points the schema at the Mechanic model to derive fields from."""

        model = Mechanic
        load_instance = False

    id = ma.auto_field(dump_only=True)


mechanic_schema = MechanicSchema()
mechanics_schema = MechanicSchema(many=True)
