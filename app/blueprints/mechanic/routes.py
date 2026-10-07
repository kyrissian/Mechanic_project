"""
CRUD routes for the Mechanic resource, plus authentication and
ticket-count insight endpoints.

Duplicate-email checks and the salary-excluding sort summaries live
in app/services/mechanic_service.py; routes handle auth, pagination,
and response shaping.

Creating, updating, deleting, and listing every mechanic (GET "") are
manager-only: a shop's roster -- and everyone's salary, touched by
both the full list and the update route -- is management information.
A regular mechanic can look up their OWN profile only; the three
sort endpoints are open to any logged-in mechanic.

Caching: get_mechanics is the one cached route in this app, using
query_string=True so each page/page_size combination is cached under
its own key -- Flask-Caching's key does NOT vary by query string
unless asked. Writes call cache.clear() rather than deleting a single
key, since GET /mechanics is the only cached route anywhere in the
app. Authentication runs BEFORE caching, since Flask-Caching's key is
based on the path, not who's asking -- if caching ran first, a
response computed for one authenticated request could be served to a
later, unauthenticated one.
"""

from flask import request, jsonify
from marshmallow import ValidationError
from sqlalchemy import select
from werkzeug.security import check_password_hash, generate_password_hash

from app.extensions import cache, db, limiter
from app.models.mechanic import Mechanic
from app.services import mechanic_service
from app.blueprints.mechanic import mechanic_bp
from app.blueprints.mechanic.schemas import (
    login_schema,
    mechanic_schema,
    mechanics_schema,
)
from app.blueprints.service_ticket.schemas import CLOSED_STATUSES, OPEN_STATUSES
from app.utils.errors import validation_error_response
from app.utils.pagination import paginate_query
from app.utils.util import encode_mechanic_token, manager_required, mechanic_token_required


@mechanic_bp.route("", methods=["POST"])
@limiter.limit("5 per hour")
@manager_required
def create_mechanic(_manager_id):
    """A mechanic account can't self-register -- only a manager can
    add staff."""
    try:
        mechanic_data = mechanic_schema.load(request.json)
    except ValidationError as e:
        return validation_error_response(e)

    if mechanic_service.email_taken(mechanic_data["email"]):
        return jsonify({"error": "Email already associated with an account."}), 400

    plaintext_password = mechanic_data.pop("password")
    new_mechanic = Mechanic(
        **mechanic_data, password_hash=generate_password_hash(plaintext_password)
    )
    db.session.add(new_mechanic)
    db.session.commit()
    cache.clear()
    return mechanic_schema.jsonify(new_mechanic), 201


@mechanic_bp.route("/login", methods=["POST"])
@limiter.limit("10 per hour")
def login():
    """Rate limited to 10/hour/IP, same brute-force reasoning as
    customer login."""
    try:
        credentials = login_schema.load(request.json)
    except ValidationError as e:
        return validation_error_response(e)

    query = select(Mechanic).where(Mechanic.email == credentials["email"])
    mechanic = db.session.execute(query).scalars().first()

    if mechanic and check_password_hash(mechanic.password_hash, credentials["password"]):
        token = encode_mechanic_token(mechanic.id, mechanic.role)
        return jsonify({"status": "success", "auth_token": token}), 200

    return jsonify({"error": "Invalid email or password."}), 401


@mechanic_bp.route("", methods=["GET"])
@manager_required
@cache.cached(timeout=60, query_string=True)
def get_mechanics(_manager_id):
    """Manager-only -- the full roster including salary."""
    result = paginate_query(
        select(Mechanic), Mechanic.id, mechanics_schema, "mechanics", size_limits=(5, 25)
    )
    return jsonify(result), 200


@mechanic_bp.route("/most-tickets", methods=["GET"])
@mechanic_token_required
def get_mechanics_by_ticket_count(_mechanic_id, _role):
    """Not cached: depends on shop-wide ticket-assignment activity,
    which changes constantly."""
    order = request.args.get("order", "desc")
    mechanics = list(db.session.execute(select(Mechanic)).scalars().all())
    mechanics.sort(key=lambda m: len(m.service_tickets), reverse=order != "asc")

    result = [
        mechanic_service.mechanic_summary(m, ticket_count=len(m.service_tickets))
        for m in mechanics
    ]
    return jsonify(result), 200


@mechanic_bp.route("/open-tickets", methods=["GET"])
@mechanic_token_required
def get_mechanics_by_open_ticket_count(_mechanic_id, _role):
    """Open = Pending, In Progress, or Completed but not yet paid --
    a rough measure of current workload."""
    order = request.args.get("order", "desc")
    mechanics = list(db.session.execute(select(Mechanic)).scalars().all())
    mechanics.sort(
        key=lambda m: mechanic_service.count_tickets_by_status(m, OPEN_STATUSES),
        reverse=order != "asc",
    )

    result = [
        mechanic_service.mechanic_summary(
            m, open_ticket_count=mechanic_service.count_tickets_by_status(m, OPEN_STATUSES)
        )
        for m in mechanics
    ]
    return jsonify(result), 200


@mechanic_bp.route("/closed-tickets", methods=["GET"])
@mechanic_token_required
def get_mechanics_by_closed_ticket_count(_mechanic_id, _role):
    """Closed = Paid or Picked Up -- completed, paid-for work."""
    order = request.args.get("order", "desc")
    mechanics = list(db.session.execute(select(Mechanic)).scalars().all())
    mechanics.sort(
        key=lambda m: mechanic_service.count_tickets_by_status(m, CLOSED_STATUSES),
        reverse=order != "asc",
    )

    result = [
        mechanic_service.mechanic_summary(
            m, closed_ticket_count=mechanic_service.count_tickets_by_status(m, CLOSED_STATUSES)
        )
        for m in mechanics
    ]
    return jsonify(result), 200


@mechanic_bp.route("/<int:mechanic_id>", methods=["GET"])
@mechanic_token_required
def get_mechanic(requesting_id, role, mechanic_id):
    """A manager may look up anyone; a regular mechanic only their
    own profile -- checked before the database is even queried, so
    it can't be used to probe another mechanic's salary. Not cached:
    keying by both target id and requester would make invalidation
    unreliable."""
    if role != "manager" and requesting_id != mechanic_id:
        return jsonify({"error": "You may only view your own profile."}), 403

    mechanic = db.session.get(Mechanic, mechanic_id)
    if mechanic:
        return mechanic_schema.jsonify(mechanic), 200
    return jsonify({"error": "Mechanic not found."}), 404


@mechanic_bp.route("/<int:mechanic_id>", methods=["PUT"])
@manager_required
def update_mechanic(_manager_id, mechanic_id):
    """Updating role or salary is a roster-management decision."""
    mechanic = db.session.get(Mechanic, mechanic_id)
    if not mechanic:
        return jsonify({"error": "Mechanic not found."}), 404

    try:
        mechanic_data = mechanic_schema.load(request.json)
    except ValidationError as e:
        return validation_error_response(e)

    if mechanic_service.email_taken(mechanic_data["email"], exclude_id=mechanic_id):
        return jsonify({"error": "Email already associated with an account."}), 400

    plaintext_password = mechanic_data.pop("password")
    for key, value in mechanic_data.items():
        setattr(mechanic, key, value)
    mechanic.password_hash = generate_password_hash(plaintext_password)

    db.session.commit()
    cache.clear()
    return mechanic_schema.jsonify(mechanic), 200


@mechanic_bp.route("/<int:mechanic_id>", methods=["DELETE"])
@limiter.limit("10 per hour")
@manager_required
def delete_mechanic(_manager_id, mechanic_id):
    """Rate limited: deletion is destructive regardless of who's
    attempting it."""
    mechanic = db.session.get(Mechanic, mechanic_id)
    if not mechanic:
        return jsonify({"error": "Mechanic not found."}), 404

    db.session.delete(mechanic)
    db.session.commit()
    cache.clear()
    return (
        jsonify({"message": f"Mechanic id: {mechanic_id}, successfully deleted."}),
        200,
    )
