"""
CRUD routes for the Mechanic resource.

Registered under the /mechanics url_prefix (see app/__init__.py), so
these routes only need their path relative to that -- "" here means
"/mechanics" in the full URL, "/<int:mechanic_id>" means
"/mechanics/<id>". Per the assignment, only Create, Read-all, Update,
and Delete are required -- the single-mechanic GET below is extra
credit, added for parity with the Customer resource.
"""

from flask import request, jsonify
from marshmallow import ValidationError
from sqlalchemy import select

from app.extensions import db
from app.models.mechanic import Mechanic
from app.blueprints.mechanic import mechanic_bp
from app.blueprints.mechanic.schemas import mechanic_schema, mechanics_schema


@mechanic_bp.route("", methods=["POST"])
def create_mechanic():
    """Create a new mechanic from the JSON request body."""
    try:
        mechanic_data = mechanic_schema.load(request.json)
    except ValidationError as e:
        return jsonify(e.messages), 400

    query = select(Mechanic).where(Mechanic.email == mechanic_data["email"])
    existing_mechanic = db.session.execute(query).scalars().first()
    if existing_mechanic:
        return jsonify({"error": "Email already associated with an account."}), 400

    new_mechanic = Mechanic(**mechanic_data)
    db.session.add(new_mechanic)
    db.session.commit()
    return mechanic_schema.jsonify(new_mechanic), 201


@mechanic_bp.route("", methods=["GET"])
def get_mechanics():
    """Retrieve every mechanic."""
    query = select(Mechanic)
    mechanics = db.session.execute(query).scalars().all()
    return mechanics_schema.jsonify(mechanics)


@mechanic_bp.route("/<int:mechanic_id>", methods=["GET"])
def get_mechanic(mechanic_id):
    """Retrieve a single mechanic by id. Not required by the
    assignment (which only lists create/get-all/update/delete), added
    as extra credit for parity with the Customer resource."""
    mechanic = db.session.get(Mechanic, mechanic_id)
    if mechanic:
        return mechanic_schema.jsonify(mechanic), 200
    return jsonify({"error": "Mechanic not found."}), 404


@mechanic_bp.route("/<int:mechanic_id>", methods=["PUT"])
def update_mechanic(mechanic_id):
    """Replace an existing mechanic's fields with the JSON request body."""
    mechanic = db.session.get(Mechanic, mechanic_id)
    if not mechanic:
        return jsonify({"error": "Mechanic not found."}), 404

    try:
        mechanic_data = mechanic_schema.load(request.json)
    except ValidationError as e:
        return jsonify(e.messages), 400

    # Same duplicate-email check as create_mechanic, but excluding
    # this mechanic's own row.
    query = select(Mechanic).where(
        Mechanic.email == mechanic_data["email"], Mechanic.id != mechanic_id
    )
    existing_mechanic = db.session.execute(query).scalars().first()
    if existing_mechanic:
        return jsonify({"error": "Email already associated with an account."}), 400

    for key, value in mechanic_data.items():
        setattr(mechanic, key, value)

    db.session.commit()
    return mechanic_schema.jsonify(mechanic), 200


@mechanic_bp.route("/<int:mechanic_id>", methods=["DELETE"])
def delete_mechanic(mechanic_id):
    """Delete a mechanic by id."""
    mechanic = db.session.get(Mechanic, mechanic_id)
    if not mechanic:
        return jsonify({"error": "Mechanic not found."}), 404

    db.session.delete(mechanic)
    db.session.commit()
    return (
        jsonify({"message": f"Mechanic id: {mechanic_id}, successfully deleted."}),
        200,
    )
