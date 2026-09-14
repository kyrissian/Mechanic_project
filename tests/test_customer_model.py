"""Tests for the Customer model."""

import pytest
from app.models.customer import Customer


def test_create_customer(db):
    """A Customer with all fields set should save and be retrievable
    with those exact values intact."""
    customer = Customer(
        first_name="Jamie",
        last_name="Rivera",
        email="jamie@example.com",
        phone="555-123-4567",
        address="123 Main St",
    )
    db.session.add(customer)
    db.session.commit()

    saved = db.session.get(Customer, customer.id)

    assert saved is not None
    assert saved.first_name == "Jamie"
    assert saved.last_name == "Rivera"
    assert saved.email == "jamie@example.com"
    assert saved.phone == "555-123-4567"
    assert saved.address == "123 Main St"


def test_customer_email_must_be_unique(db):
    """Two customers can't share the same email -- the model marks
    email as unique, so the second insert should fail at the database
    level."""
    db.session.add(
        Customer(
            first_name="Jamie",
            last_name="Rivera",
            email="jamie@example.com",
        )
    )
    db.session.commit()

    db.session.add(
        Customer(
            first_name="Someone",
            last_name="Else",
            email="jamie@example.com",
        )
    )

    with pytest.raises(Exception):
        db.session.commit()
