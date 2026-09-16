"""
Shared pytest fixtures.

`app` builds a fresh Flask app configured for testing (in-memory
SQLite, per TestingConfig) and creates every registered model's table
before yielding control to the test. Tearing tables down after each
test (rather than reusing one database across the whole test run)
means tests can never leak state into each other -- one test creating
a customer can't cause a different test to unexpectedly see it.
"""

import pytest
from app import create_app
from app.extensions import db as _db
from config import TestingConfig


@pytest.fixture
def app():
    """A fresh Flask app per test, wired to an isolated in-memory
    database that's created before the test runs and dropped after."""
    flask_app = create_app(TestingConfig)

    with flask_app.app_context():
        _db.create_all()
        yield flask_app
        _db.drop_all()


# pylint: disable=redefined-outer-name,unused-argument
# `app` here is intentionally the same name as the `app` fixture above
# -- that's how pytest wires fixture dependencies together, not an
# accidental shadow. It's unused directly in the body because its job
# is just to guarantee the app/db setup above has already run before
# this fixture hands back the db object.
@pytest.fixture
def db(app):
    """The shared SQLAlchemy db instance, after the app fixture has
    already set up a fresh in-memory database for it to use."""
    return _db


# pylint: disable=redefined-outer-name
@pytest.fixture
def client(app):
    """A Flask test client for sending HTTP requests against routes,
    backed by the same fresh in-memory database as the `db` fixture."""
    return app.test_client()


def make_service_ticket_kwargs(**overrides):
    """Default field values for constructing a ServiceTicket in
    tests. Individual tests override only the fields they care about
    (e.g. `customer=` or `mechanics=`) instead of repeating every
    field each time -- this is what test_mechanic_model.py and
    test_service_ticket_model.py both use to build their tickets.
    """
    defaults = {
        "vin": "1HGCM82633A004352",
        "service_date": "2026-01-05",
        "service_desc": "Brake pad replacement",
    }
    defaults.update(overrides)
    return defaults
