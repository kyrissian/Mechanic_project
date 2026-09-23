"""
CRUD routes for the Mechanic resource.

Registered under the /mechanics url_prefix (see app/__init__.py), so
these routes only need their path relative to that -- "" here means
"/mechanics" in the full URL, "/<int:mechanic_id>" means
"/mechanics/<id>". Per the assignment, only Create, Read-all, Update,
and Delete are required -- the single-mechanic GET below is extra
credit, added for parity with the Customer resource.

Mechanic creation and deletion are rate limited, for the same reasons
as the equivalent Customer routes (see create_mechanic and
delete_mechanic). Both read routes (list and single) are cached: the
mechanic roster is read often but written to rarely, unlike Customer
or ServiceTicket, which change too often for caching to help. Every
route that changes the mechanic roster clears the relevant cache
entries after committing, so clients never see stale data through the
API -- the 60-second timeout only matters for a change made outside
the API (e.g. directly in MySQL Workbench).
"""

from flask import request, jsonify
from marshmallow import ValidationError
from sqlalchemy import select

from app.extensions import cache, db, limiter
from app.models.mechanic import Mechanic
from app.blueprints.mechanic import mechanic_bp
from app.blueprints.mechanic.schemas import mechanic_schema, mechanics_schema
from app.utils.errors import validation_error_response

# Single source of truth for the list-cache key, shared by the
# @cache.cached decorator and every cache.delete() call below. If the
# two ever drifted apart, invalidation would silently stop working.
MECHANICS_CACHE_KEY = "all_mechanics"


@mechanic_bp.route("", methods=["POST"])
@limiter.limit("5 per hour")
def create_mechanic():
    """Create a new mechanic from the JSON request body.

    Rate limited to 5 requests per hour per client IP, the same limit
    and reasoning as create_customer: creation is a write path open to
    junk records and email probing. In practice this limit never
    touches legitimate use -- a real shop has only a handful of
    mechanics to register in the first place.

    Only the list cache needs clearing here, not the single-mechanic
    cache: a brand-new mechanic's id has no existing cache entry to
    invalidate.
    """
    try:
        mechanic_data = mechanic_schema.load(request.json)
    except ValidationError as e:
        return validation_error_response(e)

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
@cache.memoize(timeout=60)
def get_mechanic(mechanic_id):
    """Retrieve a single mechanic by id. Not required by the
    assignment (which only lists create/get-all/update/delete), added
    as extra credit for parity with the Customer resource.

    Cached per id for 60 seconds, same reasoning as get_mechanics: a
    single mechanic's info is looked up often (e.g. to confirm details
    before assigning them to a ticket) and changes rarely. Uses
    memoize rather than cached() so each mechanic_id gets its own
    cache entry, which update_mechanic and delete_mechanic can clear
    individually without touching any other mechanic's cached entry.

    Known limitation: a 404 for an id that doesn't exist yet also gets
    cached. create_mechanic has no way to know in advance which id a
    new mechanic will be assigned, so it can't clear that entry ahead
    of time -- a client that guesses an unused id right before it's
    created could see a stale 404 for up to 60 seconds. Accepted as a
    narrow edge case rather than added complexity to solve it.
    """
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
        return validation_error_response(e)

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
    # Both caches now hold stale data: the list includes this mechanic's
    # old values, and their individual entry does too.
    cache.delete(MECHANICS_CACHE_KEY)
    cache.delete_memoized(get_mechanic, mechanic_id)
    return mechanic_schema.jsonify(mechanic), 200


@mechanic_bp.route("/<int:mechanic_id>", methods=["DELETE"])
@limiter.limit("10 per hour")
def delete_mechanic(mechanic_id):
    """Delete a mechanic by id.

    Rate limited to 10 requests per hour per client IP, the same limit
    and reasoning as delete_customer: deletion is destructive, so the
    limit guards against a compromised client or a buggy script
    wiping the roster, not against normal use.

    Clearing the single-mechanic cache here matters more than it might
    look: without it, GET /mechanics/<id> would keep returning a 200
    with this mechanic's last-known data for up to 60 seconds after
    they were actually deleted.
    """
    mechanic = db.session.get(Mechanic, mechanic_id)
    if not mechanic:
        return jsonify({"error": "Mechanic not found."}), 404

    db.session.delete(mechanic)
    db.session.commit()
    cache.delete(MECHANICS_CACHE_KEY)  # deleted mechanic must vanish from the list
    cache.delete_memoized(get_mechanic, mechanic_id)  # and from its own lookup
    return (
        jsonify({"message": f"Mechanic id: {mechanic_id}, successfully deleted."}),
        200,
    )
