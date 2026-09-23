"""
CRUD routes for the Customer resource, plus authentication.

Follows standard REST conventions: the same /customers endpoint
handles multiple operations, differentiated by HTTP method --
GET /customers (all), GET /customers/<id> (one), POST /customers
(create), PUT /customers/<id> (full update), DELETE /customers/<id>.

POST /customers/login exchanges email/password for a JWT (see
app/utils/util.py). GET /customers/my-tickets and both PUT/DELETE
require that token via @token_required, and the update/delete routes
additionally check the token's customer_id against the id in the URL,
so a customer can only ever modify or delete their own account.

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
from app.blueprints.customer import customer_bp
from app.blueprints.customer.schemas import customer_schema, customers_schema, login_schema
from app.blueprints.service_ticket.schemas import service_tickets_schema
from app.utils.errors import validation_error_response
from app.utils.util import encode_token, token_required


@customer_bp.route("", methods=["POST"])
@limiter.limit("5 per hour")
def create_customer():
    """Create a new customer from the JSON request body.

    Rate limited to 5 requests per hour per client IP. Creation is the
    write path most open to abuse: without a limit, a script could flood
    the database with junk customer records or probe for which emails
    are already registered. Every attempt counts toward the limit,
    including ones rejected with a 400, which is what stops that
    kind of probing.
    """
    try:
        customer_data = customer_schema.load(request.json)
    except ValidationError as e:
        return validation_error_response(e)

    query = select(Customer).where(Customer.email == customer_data["email"])
    existing_customer = db.session.execute(query).scalars().first()
    if existing_customer:
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
    """Exchange a customer's email and password for a JWT.

    Rate limited to 10 requests per hour per client IP. Login is a
    classic brute-force target -- without a limit, a script could try
    thousands of password guesses against one email address. Both
    failed and successful attempts count toward the limit.
    """
    try:
        credentials = login_schema.load(request.json)
    except ValidationError as e:
        return validation_error_response(e)

    query = select(Customer).where(Customer.email == credentials["email"])
    customer = db.session.execute(query).scalars().first()

    if customer and check_password_hash(customer.password_hash, credentials["password"]):
        token = encode_token(customer.id)
        return jsonify({"status": "success", "auth_token": token}), 200

    # Deliberately the same message whether the email doesn't exist or
    # the password is wrong -- distinguishing the two would let an
    # attacker enumerate which emails are registered.
    return jsonify({"error": "Invalid email or password."}), 401


@customer_bp.route("", methods=["GET"])
def get_customers():
    """Retrieve every customer."""
    query = select(Customer)
    customers = db.session.execute(query).scalars().all()
    return customers_schema.jsonify(customers)


@customer_bp.route("/<int:customer_id>", methods=["GET"])
def get_customer(customer_id):
    """Retrieve a single customer by id."""
    customer = db.session.get(Customer, customer_id)
    if customer:
        return customer_schema.jsonify(customer), 200
    return jsonify({"error": "Customer not found."}), 404


@customer_bp.route("/my-tickets", methods=["GET"])
@token_required
def get_my_tickets(customer_id):
    """Retrieve every service ticket belonging to the logged-in customer.

    customer_id comes from the validated token via @token_required,
    never from the URL or request body -- a customer can only ever see
    their own tickets, with no id to tamper with in the first place.
    """
    query = select(ServiceTicket).where(ServiceTicket.customer_id == customer_id)
    tickets = db.session.execute(query).scalars().all()
    return service_tickets_schema.jsonify(tickets)


@customer_bp.route("/<int:customer_id>", methods=["PUT"])
@token_required
def update_customer(token_customer_id, customer_id):
    """Replace an existing customer's fields with the JSON request body.

    Requires a valid token, and the token's customer_id must match the
    id in the URL -- checked before the database is even queried, so a
    customer can't use it to probe whether another id exists. Without
    this check, any logged-in customer could edit any other customer's
    record just by knowing their id.
    """
    if token_customer_id != customer_id:
        return jsonify({"error": "You may only update your own account."}), 403

    customer = db.session.get(Customer, customer_id)
    if not customer:
        return jsonify({"error": "Customer not found."}), 404

    try:
        customer_data = customer_schema.load(request.json)
    except ValidationError as e:
        return validation_error_response(e)

    # Same duplicate-email check as create_customer, but excluding
    # this customer's own row -- otherwise updating a customer
    # without changing their email would incorrectly flag their own
    # existing email as "already in use."
    query = select(Customer).where(
        Customer.email == customer_data["email"], Customer.id != customer_id
    )
    existing_customer = db.session.execute(query).scalars().first()
    if existing_customer:
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
    """Delete a customer by id.

    Requires a valid token matching the id being deleted, for the same
    reason as update_customer -- without it, any logged-in customer
    could delete any other customer's account. Still rate limited to
    10 requests per hour per client IP on top of that, since deletion
    is destructive regardless of whose account it targets.
    """
    if token_customer_id != customer_id:
        return jsonify({"error": "You may only delete your own account."}), 403

    customer = db.session.get(Customer, customer_id)
    if not customer:
        return jsonify({"error": "Customer not found."}), 404

    db.session.delete(customer)
    db.session.commit()
    return (
        jsonify({"message": f"Customer id: {customer_id}, successfully deleted."}),
        200,
    )
