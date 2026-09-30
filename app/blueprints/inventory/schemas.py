"""
Marshmallow schema for the Inventory model.
"""

from decimal import Decimal

from marshmallow import fields, validate

from app.extensions import ma
from app.models.inventory import Inventory


class InventorySchema(ma.SQLAlchemyAutoSchema):
    """Auto-generates fields from the Inventory model's columns."""

    class Meta:
        """Points the schema at the Inventory model to derive fields from."""

        model = Inventory
        load_instance = False

    id = ma.auto_field(dump_only=True)

    name = fields.String(required=True, validate=validate.Length(min=1, max=150))

    # price is Numeric(10, 2) in the model. as_string=True with
    # places=2 serializes it as a fixed-precision string (e.g.
    # "12.50"), so every money value in this API formats identically.
    # It still accepts an int, float, or string on input. The range
    # rejects zero/negative prices and anything the column couldn't hold.
    price = fields.Decimal(
        as_string=True,
        places=2,
        required=True,
        validate=validate.Range(min=Decimal("0.01"), max=Decimal("99999999.99")),
    )

    # How many of this part the shop has right now. Required on
    # create/update -- a manager stating stock explicitly rather than
    # it silently defaulting to some number. Decremented automatically
    # by add_part_to_ticket in the service_ticket blueprint, which
    # also refuses to over-allocate past what's in stock.
    quantity_on_hand = fields.Integer(
        required=True, validate=validate.Range(min=0, max=1_000_000)
    )


inventory_schema = InventorySchema()
inventory_list_schema = InventorySchema(many=True)
