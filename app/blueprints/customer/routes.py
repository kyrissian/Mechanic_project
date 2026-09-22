"""
CRUD routes for the Customer resource.

Follows standard REST conventions: the same /customers endpoint
handles multiple operations, differentiated by HTTP method --
GET /customers (all), GET /customers/<id> (one), POST /customers
(create), PUT /customers/<id> (full update), DELETE /customers/<id>.

Customer creation and deletion are rate limited (see create_customer
and delete_customer). Every route in the app also carries a global
default limit (200/day, 50/hour) set on the Limiter itself in
extensions.py. Customer reads are intentionally not cached: they
contain personal data and change whenever a customer is created,
updated, or deleted.
"""

from flask import request, jsonify
from marshmallow import ValidationError
from sqlalchemy import select

from app.extensions import db, limiter
from app.models.customer import Customer
from app.blueprints.customer import customer_bp
from app.blueprints.customer.schemas import customer_schema, customers_schema


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
        return jsonify(e.messages), 400

    query = select(Customer).where(Customer.email == customer_data["email"])
    existing_customer = db.session.execute(query).scalars().first()
    if existing_customer:
        return jsonify({"error": "Email already associated with an account."}), 400

    new_customer = Customer(**customer_data)
    db.session.add(new_customer)
    db.session.commit()
    return customer_schema.jsonify(new_customer), 201


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


@customer_bp.route("/<int:customer_id>", methods=["PUT"])
def update_customer(customer_id):
    """Replace an existing customer's fields with the JSON request body."""
    customer = db.session.get(Customer, customer_id)
    if not customer:
        return jsonify({"error": "Customer not found."}), 404

    try:
        customer_data = customer_schema.load(request.json)
    except ValidationError as e:
        return jsonify(e.messages), 400

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

    for key, value in customer_data.items():
        setattr(customer, key, value)

    db.session.commit()
    return customer_schema.jsonify(customer), 200


@customer_bp.route("/<int:customer_id>", methods=["DELETE"])
@limiter.limit("10 per hour")
def delete_customer(customer_id):
    """Delete a customer by id.

    Rate limited to 10 requests per hour per client IP. Deletion is the
    most destructive route on this resource, so the limit exists to
    contain a compromised client or a buggy script looping through ids
    and wiping records, not to throttle ordinary use -- a person
    manually cleaning up test data would rarely hit 10 deletes in an
    hour. As with create_customer, attempts on an id that doesn't exist
    (404) still count toward the limit.
    """
    customer = db.session.get(Customer, customer_id)
    if not customer:
        return jsonify({"error": "Customer not found."}), 404

    db.session.delete(customer)
    db.session.commit()
    return (
        jsonify({"message": f"Customer id: {customer_id}, successfully deleted."}),
        200,
    )
