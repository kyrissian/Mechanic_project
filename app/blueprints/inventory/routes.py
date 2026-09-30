"""
CRUD routes for the Inventory resource (the shop's parts catalog).

Registered under the /inventory url_prefix (see app/__init__.py).

Reading the catalog is open to any logged-in mechanic -- staff need
part names, prices, and stock levels to do their work. Creating,
updating, and deleting parts is manager-only, since prices and stock
counts are a management decision. Customers have no access at all.

A part that has been used on any ticket cannot be deleted (409),
for the same reason completed tickets can't be erased: history should
stay accurate. Renaming or repricing a part is always allowed;
tickets keep the unit_price they were given when the part was added,
so a price change never rewrites past tickets. quantity_on_hand is
also editable directly here (e.g. after receiving a new shipment),
separately from the automatic decrement that happens when a part is
added to a ticket (see add_part_to_ticket in the service_ticket
blueprint).

Not cached: quoting a job should always use the current price and
stock level, and the catalog is small enough that a cache would add
invalidation complexity for little gain.
"""

from flask import request, jsonify
from marshmallow import ValidationError
from sqlalchemy import select

from app.extensions import db, limiter
from app.models.inventory import Inventory
from app.blueprints.inventory import inventory_bp
from app.blueprints.inventory.schemas import inventory_list_schema, inventory_schema
from app.utils.errors import validation_error_response
from app.utils.pagination import paginate_query
from app.utils.util import manager_required, mechanic_token_required


def _name_taken(name, exclude_id=None):
    """Return True if another part already uses this name, compared
    case-insensitively. exclude_id lets an update ignore the part
    being updated, so keeping its own name is never a conflict."""
    query = select(Inventory).where(db.func.lower(Inventory.name) == name.lower())
    if exclude_id is not None:
        query = query.where(Inventory.id != exclude_id)
    return db.session.execute(query).scalars().first() is not None


@inventory_bp.route("", methods=["POST"])
@manager_required
def create_part(_manager_id):
    """Create a new part from the JSON request body. Manager-only."""
    try:
        part_data = inventory_schema.load(request.json)
    except ValidationError as e:
        return validation_error_response(e)

    if _name_taken(part_data["name"]):
        return jsonify({"error": "A part with that name already exists."}), 400

    new_part = Inventory(**part_data)
    db.session.add(new_part)
    db.session.commit()
    return inventory_schema.jsonify(new_part), 201


@inventory_bp.route("", methods=["GET"])
@mechanic_token_required
def get_inventory(_mechanic_id, _role):
    """Retrieve every part, paginated. Requires being logged in as
    any mechanic.

    ?page (default 1) and ?page_size (default 5, capped at 25) work
    the same way as every other paginated route -- see
    app/utils/pagination.py.
    """
    result = paginate_query(
        select(Inventory), Inventory.id, inventory_list_schema, "inventory",
        size_limits=(5, 25),
    )
    return jsonify(result), 200


@inventory_bp.route("/<int:inventory_id>", methods=["GET"])
@mechanic_token_required
def get_part(_mechanic_id, _role, inventory_id):
    """Retrieve a single part by id. Requires being logged in as any mechanic."""
    part = db.session.get(Inventory, inventory_id)
    if part:
        return inventory_schema.jsonify(part), 200
    return jsonify({"error": "Part not found."}), 404


@inventory_bp.route("/<int:inventory_id>", methods=["PUT"])
@manager_required
def update_part(_manager_id, inventory_id):
    """Replace a part's name, price, and quantity_on_hand with the
    JSON request body. Manager-only. Existing tickets keep the
    unit_price they already have; only future additions use the new
    price."""
    part = db.session.get(Inventory, inventory_id)
    if not part:
        return jsonify({"error": "Part not found."}), 404

    try:
        part_data = inventory_schema.load(request.json)
    except ValidationError as e:
        return validation_error_response(e)

    if _name_taken(part_data["name"], exclude_id=inventory_id):
        return jsonify({"error": "A part with that name already exists."}), 400

    for key, value in part_data.items():
        setattr(part, key, value)

    db.session.commit()
    return inventory_schema.jsonify(part), 200


@inventory_bp.route("/<int:inventory_id>", methods=["DELETE"])
@limiter.limit("10 per hour")
@manager_required
def delete_part(_manager_id, inventory_id):
    """Delete a part by id. Manager-only, and rate limited to 10
    requests per hour per client IP like every other delete route.
    A part already used on any ticket is refused with 409 rather than
    deleted, so past tickets never lose track of what was used."""
    part = db.session.get(Inventory, inventory_id)
    if not part:
        return jsonify({"error": "Part not found."}), 404

    if part.ticket_parts:
        return (
            jsonify(
                {"error": "This part has been used on a ticket and cannot be deleted."}
            ),
            409,
        )

    db.session.delete(part)
    db.session.commit()
    return jsonify({"message": f"Part id: {inventory_id}, successfully deleted."}), 200
