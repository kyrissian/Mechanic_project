"""
Routes for the ServiceTicket resource.

Assignment checks and stock allocation live in
app/services/service_ticket_service.py; routes handle auth, parsing,
and response shaping. Updating status and adding a part are both
open to a manager OR the mechanic assigned to that specific ticket --
not any mechanic -- since someone with no connection to a job has no
business acting on it. There is still no full PUT/DELETE on the
ticket resource itself: a completed or in-progress record should
never be silently overwritten or erased wholesale.
"""

from flask import request, jsonify
from marshmallow import ValidationError
from sqlalchemy import select

from app.extensions import db
from app.models.mechanic import Mechanic
from app.models.service_ticket import ServiceTicket
from app.models.inventory import Inventory
from app.services import service_ticket_service
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
    """Manager-only: creation sets cost and description up front,
    both otherwise manager-controlled elsewhere in this resource."""
    try:
        ticket_data = service_ticket_schema.load(request.json)
    except ValidationError as e:
        return validation_error_response(e)

    if not service_ticket_service.customer_is_active(ticket_data["customer_id"]):
        return jsonify({"error": "Customer not found."}), 404

    new_ticket = ServiceTicket(**ticket_data)
    db.session.add(new_ticket)
    db.session.commit()
    return service_ticket_schema.jsonify(new_ticket), 201


@service_ticket_bp.route("", methods=["GET"])
@mechanic_token_required
def get_service_tickets(_mechanic_id, _role):
    """Any logged-in mechanic -- staff need visibility into the full
    queue."""
    result = paginate_query(
        select(ServiceTicket), ServiceTicket.id, service_tickets_schema, "tickets",
        size_limits=(3, 30),
    )
    return jsonify(result), 200


@service_ticket_bp.route("/my-tickets", methods=["GET"])
@mechanic_token_required
def get_my_assigned_tickets(mechanic_id, _role):
    """mechanic_id comes from the validated token, never the URL --
    no id to tamper with."""
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
    """Ticket visibility is intentionally shared with every
    authenticated mechanic, so the shop can coordinate work without
    exposing data to customers or the public."""
    ticket = db.session.get(ServiceTicket, ticket_id)
    if ticket:
        return service_ticket_schema.jsonify(ticket), 200
    return jsonify({"error": "Service ticket not found."}), 404


@service_ticket_bp.route("/<int:ticket_id>", methods=["PUT"])
@manager_required
def update_ticket_details(_manager_id, ticket_id):
    """Partial update: either field alone or both, but at least one
    is required -- an empty edit is rejected rather than silently
    succeeding."""
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
    """See service_ticket_service.mechanic_is_assigned for the
    assignment rule."""
    ticket = db.session.get(ServiceTicket, ticket_id)
    if not ticket:
        return jsonify({"error": "Service ticket not found."}), 404

    if role != "manager" and not service_ticket_service.mechanic_is_assigned(
        ticket, mechanic_id
    ):
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
    """See service_ticket_service.allocate_part for the stock and
    price-snapshot rules."""
    ticket = db.session.get(ServiceTicket, ticket_id)
    if not ticket:
        return jsonify({"error": "Service ticket not found."}), 404

    if not db.session.get(Inventory, inventory_id):
        return jsonify({"error": "Part not found."}), 404

    if role != "manager" and not service_ticket_service.mechanic_is_assigned(
        ticket, requester_id
    ):
        return (
            jsonify({"error": "You may only add parts to tickets you are assigned to."}),
            403,
        )

    try:
        part_data = add_part_schema.load(request.get_json(silent=True) or {})
    except ValidationError as e:
        return validation_error_response(e)

    error, _ = service_ticket_service.allocate_part(
        ticket, inventory_id, part_data["quantity"]
    )
    if error:
        return jsonify({"error": error}), 400

    db.session.commit()
    return service_ticket_schema.jsonify(ticket), 200


@service_ticket_bp.route(
    "/<int:ticket_id>/assign-mechanic/<int:mechanic_id>", methods=["PUT"]
)
@manager_required
def assign_mechanic(_manager_id, ticket_id, mechanic_id):
    """Who works which ticket is a staffing decision, not something
    an ordinary mechanic should be able to change -- same reasoning
    as the bulk /edit route below."""
    ticket = db.session.get(ServiceTicket, ticket_id)
    if not ticket:
        return jsonify({"error": "Service ticket not found."}), 404

    mechanic = db.session.get(Mechanic, mechanic_id)
    if not mechanic:
        return jsonify({"error": "Mechanic not found."}), 404

    if mechanic in ticket.mechanics:
        return jsonify({"error": "Mechanic is already assigned to this ticket."}), 400

    ticket.mechanics.append(mechanic)
    db.session.commit()
    return service_ticket_schema.jsonify(ticket), 200


@service_ticket_bp.route(
    "/<int:ticket_id>/remove-mechanic/<int:mechanic_id>", methods=["PUT"]
)
@manager_required
def remove_mechanic(_manager_id, ticket_id, mechanic_id):
    """Manager-only."""
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


@service_ticket_bp.route("/<int:ticket_id>/edit", methods=["PUT"])
@manager_required
def edit_ticket_mechanics(_manager_id, ticket_id):
    """Idempotent by design: adding an already-assigned mechanic, or
    removing one who isn't assigned, is silently skipped rather than
    rejected -- appropriate for a bulk operation. A nonexistent
    mechanic id is still a real 404, checked for up front via
    service_ticket_service.resolve_mechanics_or_error."""
    ticket = db.session.get(ServiceTicket, ticket_id)
    if not ticket:
        return jsonify({"error": "Service ticket not found."}), 404

    try:
        edit_data = ticket_mechanic_edit_schema.load(request.json)
    except ValidationError as e:
        return validation_error_response(e)

    to_add, missing_id = service_ticket_service.resolve_mechanics_or_error(
        edit_data["add_ids"]
    )
    if missing_id is not None:
        return jsonify({"error": f"Mechanic id {missing_id} not found."}), 404

    to_remove, missing_id = service_ticket_service.resolve_mechanics_or_error(
        edit_data["remove_ids"]
    )
    if missing_id is not None:
        return jsonify({"error": f"Mechanic id {missing_id} not found."}), 404

    for mechanic in to_add:
        if mechanic not in ticket.mechanics:
            ticket.mechanics.append(mechanic)

    for mechanic in to_remove:
        if mechanic in ticket.mechanics:
            ticket.mechanics.remove(mechanic)

    db.session.commit()
    return service_ticket_schema.jsonify(ticket), 200
