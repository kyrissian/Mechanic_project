"""
Routes for the ServiceTicket resource.

Registered under the /service-tickets url_prefix (see app/__init__.py).

Every route here now requires mechanic authentication (see
app/utils/util.py). Creating a ticket, editing its description/cost,
and assigning/removing mechanics (both the single-action and bulk
routes) are all manager-only -- these are the same actions that were
already reasoned as management decisions on the Mechanic side
(creation, roster changes), applied consistently here. Updating a
ticket's status is open to a manager OR a mechanic who is actually
assigned to that ticket -- a mechanic with no connection to a job has
no business changing its status, so this is checked the same way
add_part_to_ticket already checks assignment. Adding a part to a
ticket is open to a manager or a mechanic assigned to that ticket, and
also refuses to allocate more of a part than the shop currently has in
stock (see add_part_to_ticket), decrementing Inventory.quantity_on_hand
by whatever is actually allocated. Reading the ticket list/single
ticket is open to any logged-in mechanic -- staff need visibility into
the whole queue. There is still no PUT/DELETE for the ticket resource
itself (beyond the scoped description/cost/status routes below) -- a
completed or in-progress service record should never be silently
overwritten or erased wholesale.

Customers never touch this blueprint directly: their own read-only
view of their tickets lives at GET /customers/my-tickets in the
customer blueprint, not here.
"""

from flask import request, jsonify
from marshmallow import ValidationError
from sqlalchemy import select

from app.extensions import db
from app.models.customer import Customer
from app.models.inventory import Inventory
from app.models.service_ticket import ServiceTicket
from app.models.mechanic import Mechanic
from app.models.ticket_part import TicketPart
from app.blueprints.service_ticket import service_ticket_bp
from app.blueprints.service_ticket.schemas import (
    add_part_schema,
    service_ticket_schema,
    service_tickets_schema,
    status_update_schema,
    ticket_details_update_schema,
    ticket_mechanic_edit_schema,
)
from app.utils.errors import validation_error_response
from app.utils.pagination import paginate_query
from app.utils.util import manager_required, mechanic_token_required


@service_ticket_bp.route("", methods=["POST"])
@manager_required
def create_service_ticket(_manager_id):
    """Create a new service ticket from the JSON request body.

    Manager-only: creation sets the ticket's cost and description up
    front, both of which are otherwise manager-controlled everywhere
    else in this blueprint, so gating creation the same way keeps
    that consistent rather than letting any mechanic create a ticket
    only for a manager to immediately have to fix its price.
    """
    try:
        ticket_data = service_ticket_schema.load(request.json)
    except ValidationError as e:
        return validation_error_response(e)

    # Explicit check rather than relying on the database's own foreign
    # key enforcement: MySQL (production) would reject an invalid
    # customer_id, but our test database (SQLite) does not enforce
    # foreign keys by default, so relying on the database alone would
    # let this bug through in tests while only surfacing in
    # production as an unhelpful generic error. Checking here also
    # means the response is a clean 404 either way, not a raw
    # IntegrityError caught by the global error handler.
    customer = db.session.get(Customer, ticket_data["customer_id"])
    if not customer or not customer.is_active:
        return jsonify({"error": "Customer not found."}), 404

    new_ticket = ServiceTicket(**ticket_data)
    db.session.add(new_ticket)
    db.session.commit()
    return service_ticket_schema.jsonify(new_ticket), 201


@service_ticket_bp.route("", methods=["GET"])
@mechanic_token_required
def get_service_tickets(_mechanic_id, _role):
    """Retrieve every service ticket, paginated. Requires being
    logged in as any mechanic -- staff need visibility into the full
    queue.

    ?page (default 1) and ?page_size (default 3, capped at 30) work
    the same way as every other paginated route -- see
    app/utils/pagination.py. The small default reflects how much each
    ticket carries: status, cost, assigned mechanics, and a parts
    list with quantities and line totals.
    """
    result = paginate_query(
        select(ServiceTicket), ServiceTicket.id, service_tickets_schema, "tickets",
        size_limits=(3, 30),
    )
    return jsonify(result), 200


@service_ticket_bp.route("/my-tickets", methods=["GET"])
@mechanic_token_required
def get_my_assigned_tickets(mechanic_id, _role):
    """Retrieve service tickets the logged-in mechanic is personally
    assigned to, paginated -- the mechanic-side counterpart to
    GET /customers/my-tickets. mechanic_id comes from the validated
    token, never a URL parameter, so there's no id to tamper with.

    ?page (default 1) and ?page_size (default 2, capped at 20) work
    the same way as the customer version -- see
    app/utils/pagination.py.

    Queries ServiceTicket directly (joined through the mechanics
    relationship) rather than reading mechanic.service_tickets off a
    loaded Mechanic object, since the latter doesn't support
    offset/limit pagination cleanly.
    """
    query = (
        select(ServiceTicket)
        .join(ServiceTicket.mechanics)
        .where(Mechanic.id == mechanic_id)
    )
    result = paginate_query(
        query, ServiceTicket.id, service_tickets_schema, "tickets", size_limits=(2, 20)
    )
    return jsonify(result), 200


@service_ticket_bp.route("/<int:ticket_id>", methods=["GET"])
@mechanic_token_required
def get_service_ticket(_mechanic_id, _role, ticket_id):
    """Retrieve a single service ticket by id. Requires being logged
    in as any mechanic -- extra credit for parity with Customer and
    Mechanic, not required by the assignment."""
    ticket = db.session.get(ServiceTicket, ticket_id)
    if ticket:
        return service_ticket_schema.jsonify(ticket), 200
    return jsonify({"error": "Service ticket not found."}), 404


@service_ticket_bp.route("/<int:ticket_id>", methods=["PUT"])
@manager_required
def update_ticket_details(_manager_id, ticket_id):
    """Update a ticket's description and/or cost. Manager-only.

    A partial update: either field may be sent alone, or both
    together, but the request body must include at least one -- an
    empty edit is rejected rather than silently succeeding and
    changing nothing.
    """
    ticket = db.session.get(ServiceTicket, ticket_id)
    if not ticket:
        return jsonify({"error": "Service ticket not found."}), 404

    try:
        update_data = ticket_details_update_schema.load(request.json)
    except ValidationError as e:
        return validation_error_response(e)

    if not update_data:
        return jsonify({"error": "Provide service_desc and/or cost to update."}), 400

    for key, value in update_data.items():
        setattr(ticket, key, value)

    db.session.commit()
    return service_ticket_schema.jsonify(ticket), 200


@service_ticket_bp.route("/<int:ticket_id>/status", methods=["PUT"])
@mechanic_token_required
def update_ticket_status(mechanic_id, role, ticket_id):
    """Update a ticket's status. Allowed for a manager (overall
    authority over every ticket), or for a mechanic who is actually
    assigned to this specific ticket (403 otherwise) -- a mechanic
    with no connection to a job has no business changing its status.
    Checked the same way add_part_to_ticket checks assignment.
    """
    ticket = db.session.get(ServiceTicket, ticket_id)
    if not ticket:
        return jsonify({"error": "Service ticket not found."}), 404

    if role != "manager":
        mechanic = db.session.get(Mechanic, mechanic_id)
        if mechanic not in ticket.mechanics:
            return (
                jsonify(
                    {"error": "You may only update the status of tickets you are assigned to."}
                ),
                403,
            )

    try:
        status_data = status_update_schema.load(request.json)
    except ValidationError as e:
        return validation_error_response(e)

    ticket.status = status_data["status"]
    db.session.commit()
    return service_ticket_schema.jsonify(ticket), 200


@service_ticket_bp.route(
    "/<int:ticket_id>/add-part/<int:inventory_id>", methods=["PUT"]
)
@mechanic_token_required
def add_part_to_ticket(requester_id, role, ticket_id, inventory_id):
    """Add a part to a ticket. Open to a manager, or to a mechanic
    who is assigned to this ticket (403 otherwise).

    The body is optional: {"quantity": n} adds n of the part
    (default 1). If the part is already on the ticket, its quantity
    is increased instead of creating a second line. When a part is
    first added, its current catalog price is copied onto the line
    as unit_price, so later price changes never alter this ticket;
    the line keeps that original price even if more are added later.

    Refuses to allocate more of a part than the shop currently has in
    stock (400, naming how many are actually available), and
    decrements Inventory.quantity_on_hand by whatever is allocated --
    so stock levels stay accurate automatically rather than depending
    on a manager remembering to update them by hand after every job.
    """
    ticket = db.session.get(ServiceTicket, ticket_id)
    if not ticket:
        return jsonify({"error": "Service ticket not found."}), 404

    part = db.session.get(Inventory, inventory_id)
    if not part:
        return jsonify({"error": "Part not found."}), 404

    if role != "manager":
        mechanic = db.session.get(Mechanic, requester_id)
        if mechanic not in ticket.mechanics:
            return (
                jsonify({"error": "You may only add parts to tickets you are assigned to."}),
                403,
            )

    try:
        # get_json(silent=True) so a request with no body at all is
        # fine (quantity defaults to 1) instead of raising a 415.
        part_data = add_part_schema.load(request.get_json(silent=True) or {})
    except ValidationError as e:
        return validation_error_response(e)

    requested_quantity = part_data["quantity"]
    if requested_quantity > part.quantity_on_hand:
        return (
            jsonify(
                {
                    "error": (
                        f"Not enough {part.name} in stock. "
                        f"Requested {requested_quantity}, only "
                        f"{part.quantity_on_hand} available."
                    )
                }
            ),
            400,
        )

    line = db.session.get(TicketPart, (ticket_id, inventory_id))
    if line:
        line.quantity += requested_quantity
    else:
        db.session.add(
            TicketPart(
                ticket_id=ticket_id,
                inventory_id=inventory_id,
                quantity=requested_quantity,
                unit_price=part.price,
            )
        )
    part.quantity_on_hand -= requested_quantity

    db.session.commit()
    return service_ticket_schema.jsonify(ticket), 200


@service_ticket_bp.route(
    "/<int:ticket_id>/assign-mechanic/<int:mechanic_id>", methods=["PUT"]
)
@manager_required
def assign_mechanic(_manager_id, ticket_id, mechanic_id):
    """Add a mechanic to a service ticket's list of assigned
    mechanics. Manager-only, for the same reasoning as the bulk
    /edit route below."""
    ticket = db.session.get(ServiceTicket, ticket_id)
    if not ticket:
        return jsonify({"error": "Service ticket not found."}), 404

    mechanic = db.session.get(Mechanic, mechanic_id)
    if not mechanic:
        return jsonify({"error": "Mechanic not found."}), 404

    if mechanic in ticket.mechanics:
        return jsonify({"error": "Mechanic is already assigned to this ticket."}), 400

    # The relationship attribute behaves like a plain Python list, so
    # appending here is all it takes to create the row in the
    # service_mechanics junction table -- no manual insert needed.
    ticket.mechanics.append(mechanic)
    db.session.commit()
    return service_ticket_schema.jsonify(ticket), 200


@service_ticket_bp.route(
    "/<int:ticket_id>/remove-mechanic/<int:mechanic_id>", methods=["PUT"]
)
@manager_required
def remove_mechanic(_manager_id, ticket_id, mechanic_id):
    """Remove a mechanic from a service ticket's list of assigned
    mechanics. Manager-only, for the same reasoning as assign_mechanic."""
    ticket = db.session.get(ServiceTicket, ticket_id)
    if not ticket:
        return jsonify({"error": "Service ticket not found."}), 404

    mechanic = db.session.get(Mechanic, mechanic_id)
    if not mechanic:
        return jsonify({"error": "Mechanic not found."}), 404

    if mechanic not in ticket.mechanics:
        return jsonify({"error": "Mechanic is not assigned to this ticket."}), 400

    ticket.mechanics.remove(mechanic)
    db.session.commit()
    return service_ticket_schema.jsonify(ticket), 200


def _resolve_mechanics_or_404(mechanic_ids):
    """Look up every mechanic id in the given list. Returns (list of
    Mechanic objects, None) if all exist, or (None, error_response)
    for the FIRST id that doesn't -- used by edit_ticket_mechanics
    below to validate both add_ids and remove_ids up front, before
    changing anything, so a bad id in either list never leaves the
    ticket half-updated.
    """
    mechanics = []
    for mechanic_id in mechanic_ids:
        mechanic = db.session.get(Mechanic, mechanic_id)
        if not mechanic:
            return None, (
                jsonify({"error": f"Mechanic id {mechanic_id} not found."}),
                404,
            )
        mechanics.append(mechanic)
    return mechanics, None


@service_ticket_bp.route("/<int:ticket_id>/edit", methods=["PUT"])
@manager_required
def edit_ticket_mechanics(_manager_id, ticket_id):
    """Bulk add and/or remove mechanics from a ticket in one request,
    via add_ids and remove_ids in the JSON body. Manager-only.

    Idempotent by design, unlike the single-action assign/remove
    routes above: adding a mechanic who's already assigned, or
    removing one who isn't, is silently skipped rather than treated
    as an error -- appropriate for a bulk operation, where failing an
    entire batch over one redundant id in a list of ten would be
    needlessly strict. A mechanic id that doesn't exist AT ALL is
    still a real error (404), and is checked for up front, before any
    change is applied, so a bad id never leaves the ticket
    half-updated.
    """
    ticket = db.session.get(ServiceTicket, ticket_id)
    if not ticket:
        return jsonify({"error": "Service ticket not found."}), 404

    try:
        edit_data = ticket_mechanic_edit_schema.load(request.json)
    except ValidationError as e:
        return validation_error_response(e)

    to_add, error = _resolve_mechanics_or_404(edit_data["add_ids"])
    if error:
        return error

    to_remove, error = _resolve_mechanics_or_404(edit_data["remove_ids"])
    if error:
        return error

    for mechanic in to_add:
        if mechanic not in ticket.mechanics:
            ticket.mechanics.append(mechanic)

    for mechanic in to_remove:
        if mechanic in ticket.mechanics:
            ticket.mechanics.remove(mechanic)

    db.session.commit()
    return service_ticket_schema.jsonify(ticket), 200
