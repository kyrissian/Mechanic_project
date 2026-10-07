"""
CRUD routes for the Inventory resource (the shop's parts catalog).

Duplicate-name and used-part-deletion checks live in
app/services/inventory_service.py. Reading the catalog is open to any
logged-in mechanic; creating, updating, and deleting parts is
manager-only, since prices and stock levels are a management
decision. Not cached: quoting a job should always use the current
price and stock level.
"""

from flask import request, jsonify
from marshmallow import ValidationError
from sqlalchemy import select

from app.extensions import db, limiter
from app.models.inventory import Inventory
from app.services import inventory_service
from app.blueprints.inventory import inventory_bp
from app.blueprints.inventory.schemas import inventory_list_schema, inventory_schema
from app.utils.errors import validation_error_response
from app.utils.pagination import paginate_query
from app.utils.util import manager_required, mechanic_token_required


@inventory_bp.route("", methods=["POST"])
@manager_required
def create_part(_manager_id):
    """Prices and stock levels are management decisions, so only
    managers may add to the catalog."""
    try:
        part_data = inventory_schema.load(request.json)
    except ValidationError as e:
        return validation_error_response(e)

    if inventory_service.name_taken(part_data["name"]):
        return jsonify({"error": "A part with that name already exists."}), 400

    new_part = Inventory(**part_data)
    db.session.add(new_part)
    db.session.commit()
    return inventory_schema.jsonify(new_part), 201


@inventory_bp.route("", methods=["GET"])
@mechanic_token_required
def get_inventory(_mechanic_id, _role):
    """Mechanics need current part data when they quote jobs, so the
    catalog is readable by any authenticated mechanic."""
    result = paginate_query(
        select(Inventory), Inventory.id, inventory_list_schema, "inventory",
        size_limits=(5, 25),
    )
    return jsonify(result), 200


@inventory_bp.route("/<int:inventory_id>", methods=["GET"])
@mechanic_token_required
def get_part(_mechanic_id, _role, inventory_id):
    """Any logged-in mechanic."""
    part = db.session.get(Inventory, inventory_id)
    if part:
        return inventory_schema.jsonify(part), 200
    return jsonify({"error": "Part not found."}), 404


@inventory_bp.route("/<int:inventory_id>", methods=["PUT"])
@manager_required
def update_part(_manager_id, inventory_id):
    """Existing tickets keep the unit_price they already have; only
    future additions use the new price."""
    part = db.session.get(Inventory, inventory_id)
    if not part:
        return jsonify({"error": "Part not found."}), 404

    try:
        part_data = inventory_schema.load(request.json)
    except ValidationError as e:
        return validation_error_response(e)

    if inventory_service.name_taken(part_data["name"], exclude_id=inventory_id):
        return jsonify({"error": "A part with that name already exists."}), 400

    for key, value in part_data.items():
        setattr(part, key, value)

    db.session.commit()
    return inventory_schema.jsonify(part), 200


@inventory_bp.route("/<int:inventory_id>", methods=["DELETE"])
@limiter.limit("10 per hour")
@manager_required
def delete_part(_manager_id, inventory_id):
    """See inventory_service.has_been_used for why a used part can't
    be deleted."""
    part = db.session.get(Inventory, inventory_id)
    if not part:
        return jsonify({"error": "Part not found."}), 404

    if inventory_service.has_been_used(part):
        return (
            jsonify(
                {"error": "This part has been used on a ticket and cannot be deleted."}
            ),
            409,
        )

    db.session.delete(part)
    db.session.commit()
    return jsonify({"message": f"Part id: {inventory_id}, successfully deleted."}), 200
