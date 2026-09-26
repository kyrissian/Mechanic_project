"""
CRUD routes for the Mechanic resource, plus authentication and
ticket-count insight endpoints.

Registered under the /mechanics url_prefix (see app/__init__.py), so
these routes only need their path relative to that.

Every mechanic action beyond login now requires mechanic
authentication (see app/utils/util.py). Creating, updating, deleting,
and listing every mechanic (GET "") are all manager-only: a shop's
roster -- and everyone's salary, which the full list and update route
both touch -- is management information, not something a regular
mechanic should see or change about anyone but themselves. A regular
mechanic can look up their OWN profile only (see get_mechanic's
ownership check); the three ticket-count sort endpoints are open to
any logged-in mechanic, but deliberately exclude salary from their
response (see _mechanic_summary), since sorting by workload doesn't
require seeing anyone's pay.

Caching: the mechanic-list cache (get_mechanics) is unchanged, but
the single-mechanic cache has been removed entirely. @cache.memoize
keys its cache entries by the decorated function's actual arguments --
once get_mechanic also received the *requesting* mechanic's id and
role from mechanic_token_required, every different requester would
get their own separate cache entry for the same target mechanic, and
cache.delete_memoized() (used by update/delete to invalidate) could
no longer reliably clear them all, since it can't know every
requesting id/role combination that might have cached a given
target. Given this route is now authenticated internal traffic
rather than public, high-volume traffic, the caching benefit no
longer outweighed that complexity.

Decorator order also matters for correctness, not just cleanliness:
authentication must run BEFORE caching on every cached route
(get_mechanics below). Flask-Caching's cache key is based on the
request path, not on who's asking -- if caching ran first, a cached
response computed for one authenticated request could be served to a
LATER, completely unauthenticated request hitting the same path.
Putting @manager_required above @cache.cached guarantees every
request re-checks the token before the cache is ever consulted.
"""

from flask import request, jsonify
from marshmallow import ValidationError
from sqlalchemy import select
from werkzeug.security import check_password_hash, generate_password_hash

from app.extensions import cache, db, limiter
from app.models.mechanic import Mechanic
from app.blueprints.mechanic import mechanic_bp
from app.blueprints.mechanic.schemas import (
    login_schema,
    mechanic_schema,
    mechanics_schema,
)
from app.blueprints.service_ticket.schemas import CLOSED_STATUSES, OPEN_STATUSES
from app.utils.errors import validation_error_response
from app.utils.util import encode_mechanic_token, manager_required, mechanic_token_required

# Single source of truth for the list-cache key, shared by the
# @cache.cached decorator and every cache.delete() call below. If the
# two ever drifted apart, invalidation would silently stop working.
MECHANICS_CACHE_KEY = "all_mechanics"


@mechanic_bp.route("", methods=["POST"])
@limiter.limit("5 per hour")
@manager_required
def create_mechanic(_manager_id):
    """Create a new mechanic from the JSON request body.

    Manager-only: unlike Customer, a mechanic account can't
    self-register at all -- only an existing manager can add staff.
    Rate limited to 5 requests per hour per client IP on top of that,
    same reasoning as create_customer. The limiter is checked before
    the manager check (it's the outer decorator), so repeated
    unauthorized attempts still count toward the limit.
    """
    try:
        mechanic_data = mechanic_schema.load(request.json)
    except ValidationError as e:
        return validation_error_response(e)

    query = select(Mechanic).where(Mechanic.email == mechanic_data["email"])
    existing_mechanic = db.session.execute(query).scalars().first()
    if existing_mechanic:
        return jsonify({"error": "Email already associated with an account."}), 400

    plaintext_password = mechanic_data.pop("password")
    new_mechanic = Mechanic(
        **mechanic_data, password_hash=generate_password_hash(plaintext_password)
    )
    db.session.add(new_mechanic)
    db.session.commit()
    cache.delete(MECHANICS_CACHE_KEY)  # roster changed; drop the cached list
    return mechanic_schema.jsonify(new_mechanic), 201


@mechanic_bp.route("/login", methods=["POST"])
@limiter.limit("10 per hour")
def login():
    """Exchange a mechanic's email and password for a JWT carrying
    their role. Rate limited to 10 requests per hour per client IP,
    same reasoning as customer login: a classic brute-force target.
    """
    try:
        credentials = login_schema.load(request.json)
    except ValidationError as e:
        return validation_error_response(e)

    query = select(Mechanic).where(Mechanic.email == credentials["email"])
    mechanic = db.session.execute(query).scalars().first()

    if mechanic and check_password_hash(mechanic.password_hash, credentials["password"]):
        token = encode_mechanic_token(mechanic.id, mechanic.role)
        return jsonify({"status": "success", "auth_token": token}), 200

    # Same reasoning as customer login: identical message whether the
    # email doesn't exist or the password is wrong, so a client can't
    # enumerate which emails belong to real accounts.
    return jsonify({"error": "Invalid email or password."}), 401


@mechanic_bp.route("", methods=["GET"])
@manager_required
@cache.cached(timeout=60, key_prefix=MECHANICS_CACHE_KEY)
def get_mechanics(_manager_id):
    """Retrieve every mechanic, including salary. Manager-only: a
    regular mechanic has no legitimate reason to see every other
    mechanic's pay -- only a manager, who already sets salaries via
    update_mechanic, needs this view.

    Cached for 60 seconds (see module docstring for why auth must be
    the outer decorator on a cached route).
    """
    query = select(Mechanic)
    mechanics = db.session.execute(query).scalars().all()
    return mechanics_schema.jsonify(mechanics)


def _mechanic_summary(mechanic, **extra_fields):
    """Build a mechanic's public-facing summary: id and name only --
    deliberately excludes salary. Shared by the three sort endpoints
    below, so a regular mechanic can use sorting/insight views without
    ever seeing anyone's pay, including their own via this endpoint
    (their own salary is still visible through GET /mechanics/<own_id>).
    """
    return {"id": mechanic.id, "name": mechanic.name, **extra_fields}


@mechanic_bp.route("/most-tickets", methods=["GET"])
@mechanic_token_required
def get_mechanics_by_ticket_count(_mechanic_id, _role):
    """Retrieve every mechanic sorted by total number of tickets
    they've ever worked, most first by default. Available to any
    logged-in mechanic; response excludes salary (see _mechanic_summary).

    Not cached: it depends on ticket-assignment activity across the
    whole shop, which changes every time a ticket is created or a
    mechanic is added/removed from one -- the same reasoning that
    keeps ServiceTicket routes uncached elsewhere in this project.

    ?order=asc reverses to least tickets first.
    """
    order = request.args.get("order", "desc")
    query = select(Mechanic)
    mechanics = list(db.session.execute(query).scalars().all())
    mechanics.sort(key=lambda m: len(m.service_tickets), reverse=order != "asc")

    result = [
        _mechanic_summary(m, ticket_count=len(m.service_tickets))
        for m in mechanics
    ]
    return jsonify(result), 200


def _count_tickets_by_status(mechanic, statuses):
    """Count how many of a mechanic's tickets currently have a status
    in the given list. Shared by the open- and closed-ticket sort
    endpoints below.
    """
    return len([t for t in mechanic.service_tickets if t.status in statuses])


@mechanic_bp.route("/open-tickets", methods=["GET"])
@mechanic_token_required
def get_mechanics_by_open_ticket_count(_mechanic_id, _role):
    """Retrieve every mechanic sorted by how many currently OPEN
    tickets (Pending, In Progress, or Completed but not yet paid)
    they're assigned to, most first by default -- a rough measure of
    current workload. Available to any logged-in mechanic; response
    excludes salary (see _mechanic_summary).

    ?order=asc reverses to fewest open tickets first.
    """
    order = request.args.get("order", "desc")
    query = select(Mechanic)
    mechanics = list(db.session.execute(query).scalars().all())
    mechanics.sort(
        key=lambda m: _count_tickets_by_status(m, OPEN_STATUSES),
        reverse=order != "asc",
    )

    result = [
        _mechanic_summary(
            m, open_ticket_count=_count_tickets_by_status(m, OPEN_STATUSES)
        )
        for m in mechanics
    ]
    return jsonify(result), 200


@mechanic_bp.route("/closed-tickets", methods=["GET"])
@mechanic_token_required
def get_mechanics_by_closed_ticket_count(_mechanic_id, _role):
    """Retrieve every mechanic sorted by how many closed tickets
    (Paid or Picked Up) they've worked, most first by default -- a
    rough measure of completed, paid-for work. Available to any
    logged-in mechanic; response excludes salary (see
    _mechanic_summary).

    ?order=asc reverses to fewest closed tickets first.
    """
    order = request.args.get("order", "desc")
    query = select(Mechanic)
    mechanics = list(db.session.execute(query).scalars().all())
    mechanics.sort(
        key=lambda m: _count_tickets_by_status(m, CLOSED_STATUSES),
        reverse=order != "asc",
    )

    result = [
        _mechanic_summary(
            m, closed_ticket_count=_count_tickets_by_status(m, CLOSED_STATUSES)
        )
        for m in mechanics
    ]
    return jsonify(result), 200


@mechanic_bp.route("/<int:mechanic_id>", methods=["GET"])
@mechanic_token_required
def get_mechanic(requesting_id, role, mechanic_id):
    """Retrieve a single mechanic by id, including salary.

    A manager may look up any mechanic. A regular mechanic may only
    look up their OWN profile -- checked before the database is even
    queried, so a mechanic can't use this to probe another mechanic's
    salary or account details. No longer cached (see module docstring).
    """
    if role != "manager" and requesting_id != mechanic_id:
        return jsonify({"error": "You may only view your own profile."}), 403

    mechanic = db.session.get(Mechanic, mechanic_id)
    if mechanic:
        return mechanic_schema.jsonify(mechanic), 200
    return jsonify({"error": "Mechanic not found."}), 404


@mechanic_bp.route("/<int:mechanic_id>", methods=["PUT"])
@manager_required
def update_mechanic(_manager_id, mechanic_id):
    """Replace an existing mechanic's fields with the JSON request
    body. Manager-only: updating a mechanic's role or salary is a
    roster-management decision, same reasoning as create_mechanic.
    """
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

    plaintext_password = mechanic_data.pop("password")
    for key, value in mechanic_data.items():
        setattr(mechanic, key, value)
    mechanic.password_hash = generate_password_hash(plaintext_password)

    db.session.commit()
    cache.delete(MECHANICS_CACHE_KEY)  # list now holds this mechanic's old values
    return mechanic_schema.jsonify(mechanic), 200


@mechanic_bp.route("/<int:mechanic_id>", methods=["DELETE"])
@limiter.limit("10 per hour")
@manager_required
def delete_mechanic(_manager_id, mechanic_id):
    """Delete a mechanic by id. Manager-only, for the same reasoning
    as create_mechanic/update_mechanic. Still rate limited to 10
    requests per hour per client IP on top of that, since deletion is
    destructive regardless of who's attempting it.
    """
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
