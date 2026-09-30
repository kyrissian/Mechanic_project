"""
CRUD routes for the Customer resource, plus authentication.

Follows standard REST conventions: the same /customers endpoint
handles multiple operations, differentiated by HTTP method --
GET /customers (all), GET /customers/<id> (one), POST /customers
(create), PUT /customers/<id> (full update), DELETE /customers/<id>.

POST /customers/login exchanges email/password for a JWT (see
app/utils/util.py). GET /customers/my-tickets and both PUT/DELETE
require a customer token via @token_required, and the update/delete
routes additionally check the token's customer_id against the id in
the URL, so a customer can only ever modify or close their own
account. GET /customers and GET /customers/<id> require a MECHANIC
token instead (any role) -- customer records contain personal data,
so browsing or looking up other customers is staff-only, not public.

DELETE closes the account rather than erasing it, and only for a
customer with no service history. Personal details are scrubbed and
deleted_at is set, but the row stays. A customer who has ever had a
ticket cannot close their account online (409): the ticket is the
shop's business record, and letting the customer scrub the identity
attached to it would defeat its purpose. Closed accounts are hidden
from the list and single-customer lookups, can't log in, and their
tokens stop working (token_required checks).

Customer creation, deletion, and login are all rate limited (see each
function's docstring). Every route in the app also carries a global
default limit (200/day, 50/hour) set on the Limiter itself in
extensions.py. Customer reads are intentionally not cached: they
contain personal data and change whenever a customer is created,
updated, or deleted.
"""

import secrets
from datetime import datetime, timezone

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
from app.utils.pagination import paginate_query
from app.utils.util import encode_token, mechanic_token_required, token_required


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
    failed and successful attempts count toward the limit. Closed
    accounts are excluded from the lookup, so they can never log in.
    """
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

    # Deliberately the same message whether the email doesn't exist or
    # the password is wrong -- distinguishing the two would let an
    # attacker enumerate which emails are registered.
    return jsonify({"error": "Invalid email or password."}), 401


@customer_bp.route("", methods=["GET"])
@mechanic_token_required
def get_customers(_mechanic_id, _role):
    """Retrieve active customers, paginated. Requires being logged in
    as any mechanic -- customer records are personal data, not public.

    ?page (default 1) and ?page_size (default 7, capped at 50) control
    which slice is returned -- see app/utils/pagination.py. A page
    past the last real page returns an empty customers list rather
    than a 404; there's nothing wrong with the request, there's just
    no data there. Closed accounts are excluded from both the results
    and the total. Results are ordered by id so pages never overlap
    or skip.
    """
    query = select(Customer).where(Customer.deleted_at.is_(None))
    result = paginate_query(
        query, Customer.id, customers_schema, "customers", size_limits=(7, 50)
    )
    return jsonify(result), 200


@customer_bp.route("/<int:customer_id>", methods=["GET"])
@mechanic_token_required
def get_customer(_mechanic_id, _role, customer_id):
    """Retrieve a single active customer by id. Requires being
    logged in as any mechanic, same reasoning as get_customers. A
    closed account is reported as not found."""
    customer = db.session.get(Customer, customer_id)
    if customer and customer.is_active:
        return customer_schema.jsonify(customer), 200
    return jsonify({"error": "Customer not found."}), 404


@customer_bp.route("/my-tickets", methods=["GET"])
@token_required
def get_my_tickets(customer_id):
    """Retrieve service tickets belonging to the logged-in customer,
    paginated.

    customer_id comes from the validated token via @token_required,
    never from the URL or request body -- a customer can only ever see
    their own tickets, with no id to tamper with in the first place.

    ?page (default 1) and ?page_size (default 2, capped at 20) work
    the same way as GET /customers' pagination -- see
    app/utils/pagination.py. The small default is deliberate: each
    ticket now carries its status, cost, assigned mechanics, and a
    parts list with quantities and line totals, so even a handful of
    tickets is a heavier payload than it looks.
    """
    query = select(ServiceTicket).where(ServiceTicket.customer_id == customer_id)
    result = paginate_query(
        query, ServiceTicket.id, service_tickets_schema, "tickets", size_limits=(2, 20)
    )
    return jsonify(result), 200


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
    if not customer or not customer.is_active:
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
    """Close a customer's account, but only if they have no service
    history. Requires a valid token matching the id being closed, for
    the same reason as update_customer. Still rate limited to 10
    requests per hour per client IP.

    A customer with ANY ticket, in any status, gets a 409: tickets are
    the shop's business records (revenue, warranty, liability), and
    letting the customer scrub the identity attached to them would
    make those records untraceable. Shops normally keep such records
    for a legally required period, so closing an account with history
    is a matter for staff, not a self-service action.

    For a customer with no tickets this is a soft delete with
    anonymization: name, email, and phone are replaced with
    placeholders, and the password hash is replaced with a random
    hash nobody knows. The placeholder email is unique per id (email
    must stay unique) and uses the reserved .invalid domain, so it can
    never receive mail and never collides with a real address -- which
    also frees the original email to be registered again.
    """
    if token_customer_id != customer_id:
        return jsonify({"error": "You may only delete your own account."}), 403

    customer = db.session.get(Customer, customer_id)
    if not customer or not customer.is_active:
        return jsonify({"error": "Customer not found."}), 404

    has_history = db.session.execute(
        select(ServiceTicket.id).where(ServiceTicket.customer_id == customer_id).limit(1)
    ).first()
    if has_history:
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

    customer.name = "Deleted Customer"
    customer.email = f"deleted-{customer.id}@deleted.invalid"
    customer.phone = "N/A"
    customer.password_hash = generate_password_hash(secrets.token_urlsafe(32))
    # Stored as naive UTC: the column has no timezone, and MySQL's
    # DATETIME doesn't keep one either.
    customer.deleted_at = datetime.now(timezone.utc).replace(tzinfo=None)

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
