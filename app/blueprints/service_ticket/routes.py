"""
Routes for the ServiceTicket resource.

Registered under the /service-tickets url_prefix (see app/__init__.py).
Per the assignment, this resource only needs create, get-all, and the
two mechanic-assignment routes -- deliberately no update/delete for
the ticket itself, so completed work is never erased. The single-ticket
GET below is extra credit, added for parity with Customer and Mechanic.
"""

from flask import request, jsonify
from marshmallow import ValidationError
from sqlalchemy import select

from app.extensions import db
from app.models.customer import Customer
from app.models.service_ticket import ServiceTicket
from app.models.mechanic import Mechanic
from app.blueprints.service_ticket import service_ticket_bp
from app.blueprints.service_ticket.schemas import (
    service_ticket_schema,
    service_tickets_schema,
)
from app.utils.errors import validation_error_response


@service_ticket_bp.route("", methods=["POST"])
def create_service_ticket():
    """Create a new service ticket from the JSON request body."""
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
    if not customer:
        return jsonify({"error": "Customer not found."}), 404

    new_ticket = ServiceTicket(**ticket_data)
    db.session.add(new_ticket)
    db.session.commit()
    return service_ticket_schema.jsonify(new_ticket), 201


@service_ticket_bp.route("", methods=["GET"])
def get_service_tickets():
    """Retrieve every service ticket."""
    query = select(ServiceTicket)
    tickets = db.session.execute(query).scalars().all()
    return service_tickets_schema.jsonify(tickets)


@service_ticket_bp.route("/<int:ticket_id>", methods=["GET"])
def get_service_ticket(ticket_id):
    """Retrieve a single service ticket by id. Not required by the
    assignment (which only lists create/get-all/assign/remove), added
    as extra credit for parity with Customer and Mechanic."""
    ticket = db.session.get(ServiceTicket, ticket_id)
    if ticket:
        return service_ticket_schema.jsonify(ticket), 200
    return jsonify({"error": "Service ticket not found."}), 404


@service_ticket_bp.route(
    "/<int:ticket_id>/assign-mechanic/<int:mechanic_id>", methods=["PUT"]
)
def assign_mechanic(ticket_id, mechanic_id):
    """Add a mechanic to a service ticket's list of assigned mechanics."""
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
def remove_mechanic(ticket_id, mechanic_id):
    """Remove a mechanic from a service ticket's list of assigned mechanics."""
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
