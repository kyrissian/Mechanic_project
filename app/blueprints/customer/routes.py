"""
CRUD routes for the Customer resource.

Registered under the /customers url_prefix (see app/__init__.py), so
these routes only need their path relative to that -- "" here means
"/customers" in the full URL, "/<int:customer_id>" means
"/customers/<id>". Follows standard REST conventions: the same
endpoint handles multiple operations, differentiated by HTTP method.
"""

from flask import request, jsonify
from marshmallow import ValidationError
from sqlalchemy import select

from app.extensions import db
from app.models.customer import Customer
from app.blueprints.customer import customer_bp
from app.blueprints.customer.schemas import customer_schema, customers_schema


@customer_bp.route("", methods=["POST"])
def create_customer():
    """Create a new customer from the JSON request body."""
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

    for key, value in customer_data.items():
        setattr(customer, key, value)

    db.session.commit()
    return customer_schema.jsonify(customer), 200


@customer_bp.route("/<int:customer_id>", methods=["DELETE"])
def delete_customer(customer_id):
    """Delete a customer by id."""
    customer = db.session.get(Customer, customer_id)
    if not customer:
        return jsonify({"error": "Customer not found."}), 404

    db.session.delete(customer)
    db.session.commit()
    return (
        jsonify({"message": f"Customer id: {customer_id}, successfully deleted."}),
        200,
    )
