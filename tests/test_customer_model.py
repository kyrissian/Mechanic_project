"""Tests for the Customer model."""

import pytest
from app.models.customer import Customer
from tests.conftest import make_customer_kwargs


def test_create_customer(db):
    """A Customer with all fields set should save and be retrievable
    with those exact values intact."""
    customer = Customer(**make_customer_kwargs())
    db.session.add(customer)
    db.session.commit()

    saved = db.session.get(Customer, customer.id)

    assert saved is not None
    assert saved.name == "Jamie Rivera"
    assert saved.email == "jamie@example.com"
    assert saved.phone == "555-123-4567"


def test_customer_email_must_be_unique(db):
    """Two customers can't share the same email -- the model marks
    email as unique, so the second insert should fail at the database
    level."""
    db.session.add(Customer(**make_customer_kwargs()))
    db.session.commit()

    db.session.add(
        Customer(**make_customer_kwargs(name="Someone Else", phone="555-999-0000"))
    )

    with pytest.raises(Exception):
        db.session.commit()
