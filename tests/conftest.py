"""
Shared pytest fixtures.

`app` builds a fresh Flask app configured for testing (in-memory
SQLite, per TestingConfig) and creates every registered model's table
before yielding control to the test. Tearing tables down after each
test means tests can never leak state into each other.

TestingConfig switches rate limiting and caching off so the rest of
the suite is unaffected by them. rate_limited_client/cached_client opt
back in to exactly one of those features each.

Bootstrapping managers/mechanics: there is no API route to create the
first manager account (by design -- see Mechanic.role in
app/models/mechanic.py), so seed_manager() inserts one directly into
the database, bypassing the API and its password hashing route logic
(hashing the password itself with the same function the real route
uses). create_manager()/create_mechanic() build on that to log in
through the REAL /mechanics/login route afterward, so every test
still exercises real authentication rather than faking a token. The
`manager` and `mechanic` fixtures wrap the common single-account case;
call create_manager()/create_mechanic() directly when a test needs a
second, distinct account.
"""

from datetime import date
from decimal import Decimal

import pytest
from werkzeug.security import generate_password_hash

from app import create_app
from app.extensions import cache, limiter
from app.extensions import db as _db
from app.models.customer import Customer
from app.models.mechanic import Mechanic
from app.models.service_ticket import ServiceTicket
from config import TestingConfig


# Tells pytest's own test collection to skip this subfolder entirely --
# tests/unittest_suite/ holds a separate unittest-based suite (run via
# `python -m unittest discover tests`, per the course assignment), and
# without this, plain `pytest` would also collect and run those same
# tests a second time, double-counting against this suite's real
# total.
collect_ignore = ["unittest_suite"]


class RateLimitedTestConfig(TestingConfig):
    """TestingConfig with rate limiting switched back on."""

    RATELIMIT_ENABLED = True


class CachedTestConfig(TestingConfig):
    """TestingConfig with a real in-memory cache instead of NullCache."""

    CACHE_TYPE = "SimpleCache"


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


@pytest.fixture
def rate_limited_client():
    """A test client for an app with rate limiting ENABLED."""
    flask_app = create_app(RateLimitedTestConfig)

    with flask_app.app_context():
        _db.create_all()
        limiter.reset()
        yield flask_app.test_client()
        limiter.reset()
        _db.drop_all()


@pytest.fixture
def cached_client():
    """A test client for an app with a real in-memory cache ENABLED."""
    flask_app = create_app(CachedTestConfig)

    with flask_app.app_context():
        _db.create_all()
        cache.clear()
        yield flask_app.test_client()
        cache.clear()
        _db.drop_all()


def make_service_ticket_kwargs(**overrides):
    """Default field values for constructing a ServiceTicket directly
    in model-level tests. service_date is a real date object (the
    column is Date, not a string) and cost is a Decimal (the column
    is Numeric), matching the model's actual Python types rather than
    the JSON-friendly strings a route payload would use.
    """
    defaults = {
        "vin": "1HGCM82633A004352",
        "service_date": date(2026, 1, 5),
        "service_desc": "Brake pad replacement",
        "cost": Decimal("450.00"),
    }
    defaults.update(overrides)
    return defaults


def make_mechanic_kwargs(**overrides):
    """Default field values for constructing a Mechanic directly in
    the database (model-level tests, or bootstrapping an account
    outside the API). password_hash is a placeholder string unless
    overridden -- these tests don't necessarily need a working login.
    """
    defaults = {
        "name": "Alex Chen",
        "email": "alex@example.com",
        "phone": "555-987-6543",
        "salary": Decimal("55000.00"),
        "password_hash": "fakehash123",
        "role": "mechanic",
    }
    defaults.update(overrides)
    return defaults


def _name_email_for_index(index, default_name, default_email, label):
    """Shared test-data convention for generating deterministic,
    unique name/email pairs when a test needs multiple records of the
    same type."""
    if index is None:
        return default_name, default_email
    return f"{label} {index}", f"{label.lower()}{index}@example.com"


def make_mechanic_payload(index=None, **overrides):
    """Default JSON body for creating/updating a mechanic via the
    API. Pass index for a unique name/email. role defaults to
    "mechanic"."""
    name, email = _name_email_for_index(
        index,
        default_name="Alex Chen",
        default_email="alex@example.com",
        label="Mechanic",
    )

    payload = {
        "name": name,
        "email": email,
        "phone": "555-987-6543",
        "salary": 55000.00,
        "password": "wrench123",
        "role": "mechanic",
    }
    payload.update(overrides)
    return payload


def make_customer_kwargs(**overrides):
    """Default field values for constructing a Customer directly in
    the database, for model-level tests."""
    defaults = {
        "name": "Jamie Rivera",
        "email": "jamie@example.com",
        "phone": "555-123-4567",
        "password_hash": "fakehash123",
    }
    defaults.update(overrides)
    return defaults


def make_customer_payload(index=None, **overrides):
    """Default JSON body for creating/updating a customer via the API."""
    name, email = _name_email_for_index(
        index,
        default_name="Jamie Rivera",
        default_email="jamie@example.com",
        label="Customer",
    )

    payload = {
        "name": name,
        "email": email,
        "phone": "555-123-4567",
        "password": "hunter2",
    }
    payload.update(overrides)
    return payload


def login_customer(client, **overrides):  # pylint: disable=redefined-outer-name
    """Create a customer via the API, log them in, and return
    (customer_id, auth_headers)."""
    payload = make_customer_payload(**overrides)
    created = client.post("/customers", json=payload).json
    headers = auth_headers_from_login(
        client,
        "/customers/login",
        payload["email"],
        payload["password"],
    )
    return created["id"], headers


def auth_headers_from_login(client, login_path, email, password):
    """Log in through a route and return a ready Authorization
    header, so tests build Bearer headers the same way everywhere."""
    login_response = client.post(
        login_path,
        json={"email": email, "password": password},
    )
    token = login_response.json["auth_token"]
    return {"Authorization": f"Bearer {token}"}


def seed_manager(db, **overrides):  # pylint: disable=redefined-outer-name
    """Insert a manager account directly into the database, bypassing
    the API -- there is no API route to create the first manager, by
    design (see Mechanic.role in app/models/mechanic.py). Returns
    (manager, plaintext_password) so the caller can log in through
    the real API afterward. Defaults to a distinct identity from
    make_mechanic_payload()'s default, so a test that seeds a manager
    and then creates a mechanic via the API with no overrides doesn't
    collide on email.
    """
    password = overrides.pop("password", "bosspass1")
    kwargs = make_mechanic_kwargs(
        name="Morgan Lee",
        email="manager@example.com",
        role="manager",
        **overrides,
    )
    kwargs["password_hash"] = generate_password_hash(password)
    manager = Mechanic(**kwargs)
    db.session.add(manager)
    db.session.commit()
    return manager, password


def create_manager(client, db, **overrides):  # pylint: disable=redefined-outer-name
    """Bootstrap a manager account (seed_manager) and log them in
    through the real API. Returns (manager_id, auth_headers)."""
    manager_obj, password = seed_manager(db, **overrides)
    headers = auth_headers_from_login(
        client,
        "/mechanics/login",
        manager_obj.email,
        password,
    )
    return manager_obj.id, headers


def create_mechanic(client, manager_headers, **overrides):
    """Create a regular mechanic through the real API (requires a
    manager token, since mechanic creation is manager-only), then log
    them in. Returns (mechanic_id, auth_headers)."""
    payload = make_mechanic_payload(**overrides)
    created = client.post("/mechanics", json=payload, headers=manager_headers).json
    headers = auth_headers_from_login(
        client,
        "/mechanics/login",
        payload["email"],
        payload["password"],
    )
    return created["id"], headers


@pytest.fixture
def manager(client, db):  # pylint: disable=redefined-outer-name
    """A manager account and its auth headers, ready to use.
    Yields (manager_id, auth_headers)."""
    return create_manager(client, db)


@pytest.fixture
def mechanic(client, manager):  # pylint: disable=redefined-outer-name
    """A regular mechanic account and its auth headers, created via
    the manager fixture's token. Yields (mechanic_id, auth_headers)."""
    _, manager_headers = manager
    return create_mechanic(client, manager_headers)


def make_inventory_payload(index=None, **overrides):
    """Default JSON body for creating/updating a part via the API.
    Pass index for a unique name."""
    name = "Oil Filter" if index is None else f"Part {index}"
    payload = {"name": name, "price": "12.50", "quantity_on_hand": 20}
    payload.update(overrides)
    return payload


def create_part(client, manager_headers, **overrides):
    """Create a part through the real API (manager-only). Returns its id."""
    response = client.post(
        "/inventory", json=make_inventory_payload(**overrides), headers=manager_headers
    )
    return response.json["id"]


def create_ticket(client, manager_headers, customer_id=None, **overrides):
    """Create a service ticket through the real API (manager-only) and
    return its id. If no customer_id is given, a default customer is
    created first, so a test that needs two tickets must create the
    customer itself and pass customer_id to avoid a duplicate email."""
    if customer_id is None:
        customer_id = client.post("/customers", json=make_customer_payload()).json["id"]
    payload = {
        "customer_id": customer_id,
        "vin": "5YJSA1E26HF000337",
        "service_date": "2026-02-10",
        "service_desc": "Oil change and inspection",
        "cost": "120.00",
    }
    payload.update(overrides)
    return client.post(
        "/service-tickets", json=payload, headers=manager_headers
    ).json["id"]


def seed_customer_mechanic_ticket(db, **ticket_overrides):  # pylint: disable=redefined-outer-name
    """Create and commit a Customer, a Mechanic, and a ServiceTicket
    belonging to that customer, in one call. Used by tests that need
    all three objects to exist but don't care about their specific
    field values -- just that a real ticket, with a real customer,
    exists for a mechanic to be (or not be) assigned to."""
    customer = Customer(**make_customer_kwargs())
    mechanic_obj = Mechanic(**make_mechanic_kwargs())
    ticket = ServiceTicket(customer=customer, **make_service_ticket_kwargs(**ticket_overrides))
    db.session.add_all([customer, mechanic_obj, ticket])
    db.session.commit()
    return customer, mechanic_obj, ticket
