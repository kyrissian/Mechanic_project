"""
CRUD routes for the Mechanic resource.

Registered under the /mechanics url_prefix (see app/__init__.py), so
these routes only need their path relative to that -- "" here means
"/mechanics" in the full URL, "/<int:mechanic_id>" means
"/mechanics/<id>". Per the assignment, only Create, Read-all, Update,
and Delete are required -- the single-mechanic GET below is extra
credit, added for parity with the Customer resource.

The read-all route is cached (see get_mechanics). Every route that
changes the mechanic roster clears that cache after committing, so
clients never see a stale list.
"""

from flask import request, jsonify
from marshmallow import ValidationError
from sqlalchemy import select

from app.extensions import cache, db
from app.models.mechanic import Mechanic
from app.blueprints.mechanic import mechanic_bp
from app.blueprints.mechanic.schemas import mechanic_schema, mechanics_schema

# Single source of truth for the cache key, shared by the @cache.cached
# decorator and every cache.delete() call below. If the two ever drifted
# apart, invalidation would silently stop working.
MECHANICS_CACHE_KEY = "all_mechanics"


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
    cache.delete(MECHANICS_CACHE_KEY)  # roster changed; drop the cached list
    return mechanic_schema.jsonify(new_mechanic), 201


@mechanic_bp.route("", methods=["GET"])
@cache.cached(timeout=60, key_prefix=MECHANICS_CACHE_KEY)
def get_mechanics():
    """Retrieve every mechanic.

    Cached for 60 seconds. The mechanic roster changes rarely but is
    read often (e.g. whenever someone picks a mechanic to assign to a
    ticket), so most requests can be answered from memory instead of
    querying the database. The create, update, and delete routes clear
    this cache after every change, so the 60-second timeout is only a
    backstop rather than the reason data stays fresh.
    """
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
    cache.delete(MECHANICS_CACHE_KEY)  # a cached entry now holds old values
    return mechanic_schema.jsonify(mechanic), 200


@mechanic_bp.route("/<int:mechanic_id>", methods=["DELETE"])
def delete_mechanic(mechanic_id):
    """Delete a mechanic by id."""
    mechanic = db.session.get(Mechanic, mechanic_id)
    if not mechanic:
        return jsonify({"error": "Mechanic not found."}), 404

    db.session.delete(mechanic)
    db.session.commit()
    cache.delete(MECHANICS_CACHE_KEY)  # deleted mechanic must vanish from the list
    return (
        jsonify({"message": f"Mechanic id: {mechanic_id}, successfully deleted."}),
        200,
    )
