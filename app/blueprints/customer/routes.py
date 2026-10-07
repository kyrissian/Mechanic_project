"""
CRUD routes for the Customer resource, plus authentication.

Routes here handle parsing, auth/ownership, and response shaping.
The actual business rules -- duplicate-email checks, the
service-history delete policy, account anonymization -- live in
app/services/customer_service.py, callable (and testable)
independently of the HTTP layer.

POST /customers/login exchanges email/password for a JWT (see
app/utils/util.py). GET /customers/my-tickets and both PUT/DELETE
require a customer token via @token_required, and the update/delete
routes additionally check the token's customer_id against the id in
the URL, so a customer can only ever modify or close their own
account. GET /customers and GET /customers/<id> require a MECHANIC
token instead (any role) -- customer records contain personal data,
so browsing or looking up other customers is staff-only, not public.

Customer creation, deletion, and login are all rate limited (see each
function's docstring). Every route in the app also carries a global
default limit (200/day, 50/hour) set on the Limiter itself in
extensions.py. Customer reads are intentionally not cached: they
contain personal data and change whenever a customer is created,
updated, or deleted.
"""

from flask import request, jsonify
from marshmallow import ValidationError
from sqlalchemy import select
from werkzeug.security import check_password_hash, generate_password_hash

from app.extensions import db, limiter
from app.models.customer import Customer
from app.models.service_ticket import ServiceTicket
from app.services import customer_service
from app.blueprints.customer import customer_bp
from app.blueprints.customer.schemas import customer_schema, customers_schema, login_schema
from app.blueprints.service_ticket.schemas import service_tickets_schema
from app.utils.errors import validation_error_response
from app.utils.pagination import paginate_query
from app.utils.util import encode_token, mechanic_token_required, token_required


@customer_bp.route("", methods=["POST"])
@limiter.limit("5 per hour")
def create_customer():
    """Rate limited to 5/hour/IP: creation is the write path most
    open to abuse, and rejected (400) attempts still count, which is
    what stops probing for registered emails."""
    try:
        customer_data = customer_schema.load(request.json)
    except ValidationError as e:
        return validation_error_response(e)

    if customer_service.email_taken(customer_data["email"]):
        return jsonify({"error": "Email already associated with an account."}), 400

    plaintext_password = customer_data.pop("password")
    new_customer = Customer(
        **customer_data, password_hash=generate_password_hash(plaintext_password)
    )
    db.session.add(new_customer)
    db.session.commit()
    return customer_schema.jsonify(new_customer), 201


@customer_bp.route("/login", methods=["POST"])
@limiter.limit("10 per hour")
def login():
    """Rate limited to 10/hour/IP -- login is a classic brute-force
    target. Identical message for a wrong password and an
    unregistered email, so a client can't enumerate real accounts."""
    try:
        credentials = login_schema.load(request.json)
    except ValidationError as e:
        return validation_error_response(e)

    query = select(Customer).where(
        Customer.email == credentials["email"], Customer.deleted_at.is_(None)
    )
    customer = db.session.execute(query).scalars().first()

    if customer and check_password_hash(customer.password_hash, credentials["password"]):
        token = encode_token(customer.id)
        return jsonify({"status": "success", "auth_token": token}), 200

    return jsonify({"error": "Invalid email or password."}), 401


@customer_bp.route("", methods=["GET"])
@mechanic_token_required
def get_customers(_mechanic_id, _role):
    """Mechanic-only -- customer records are personal data, not
    public."""
    query = select(Customer).where(Customer.deleted_at.is_(None))
    result = paginate_query(
        query, Customer.id, customers_schema, "customers", size_limits=(7, 50)
    )
    return jsonify(result), 200


@customer_bp.route("/<int:customer_id>", methods=["GET"])
@mechanic_token_required
def get_customer(_mechanic_id, _role, customer_id):
    """Closed accounts are treated as missing so a caller can't
    distinguish "deleted" from "never existed," or probe account
    state by id."""
    customer = db.session.get(Customer, customer_id)
    if customer and customer.is_active:
        return customer_schema.jsonify(customer), 200
    return jsonify({"error": "Customer not found."}), 404


@customer_bp.route("/my-tickets", methods=["GET"])
@token_required
def get_my_tickets(customer_id):
    """customer_id comes from the validated token, never the URL --
    a customer can only ever see their own tickets, with no id to
    tamper with."""
    query = select(ServiceTicket).where(ServiceTicket.customer_id == customer_id)
    result = paginate_query(
        query, ServiceTicket.id, service_tickets_schema, "tickets", size_limits=(2, 20)
    )
    return jsonify(result), 200


@customer_bp.route("/<int:customer_id>", methods=["PUT"])
@token_required
def update_customer(token_customer_id, customer_id):
    """Token's customer_id must match the URL, checked before any
    database lookup -- a customer can't use this to probe whether
    another id exists."""
    if token_customer_id != customer_id:
        return jsonify({"error": "You may only update your own account."}), 403

    customer = db.session.get(Customer, customer_id)
    if not customer or not customer.is_active:
        return jsonify({"error": "Customer not found."}), 404

    try:
        customer_data = customer_schema.load(request.json)
    except ValidationError as e:
        return validation_error_response(e)

    if customer_service.email_taken(customer_data["email"], exclude_id=customer_id):
        return jsonify({"error": "Email already associated with an account."}), 400

    plaintext_password = customer_data.pop("password")
    for key, value in customer_data.items():
        setattr(customer, key, value)
    customer.password_hash = generate_password_hash(plaintext_password)

    db.session.commit()
    return customer_schema.jsonify(customer), 200


@customer_bp.route("/<int:customer_id>", methods=["DELETE"])
@limiter.limit("10 per hour")
@token_required
def delete_customer(token_customer_id, customer_id):
    """See customer_service.has_service_history for why this is
    refused for any account with ticket history."""
    if token_customer_id != customer_id:
        return jsonify({"error": "You may only delete your own account."}), 403

    customer = db.session.get(Customer, customer_id)
    if not customer or not customer.is_active:
        return jsonify({"error": "Customer not found."}), 404

    if customer_service.has_service_history(customer_id):
        return (
            jsonify(
                {
                    "error": (
                        "Accounts with service history can't be deleted online. "
                        "Please contact the shop."
                    )
                }
            ),
            409,
        )

    customer_service.anonymize(customer)
    db.session.commit()
    return (
        jsonify(
            {
                "message": (
                    f"Customer id: {customer_id}, account closed. "
                    "Personal details removed."
                )
            }
        ),
        200,
    )
