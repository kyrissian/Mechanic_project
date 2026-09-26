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
from app.models.mechanic import Mechanic
from config import TestingConfig


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


def make_mechanic_payload(index=None, **overrides):
    """Default JSON body for creating/updating a mechanic via the
    API. Pass index for a unique name/email. role defaults to
    "mechanic"."""
    if index is None:
        name = "Alex Chen"
        email = "alex@example.com"
    else:
        name = f"Mechanic {index}"
        email = f"mechanic{index}@example.com"

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
    if index is None:
        name = "Jamie Rivera"
        email = "jamie@example.com"
    else:
        name = f"Customer {index}"
        email = f"customer{index}@example.com"

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
    login_response = client.post(
        "/customers/login",
        json={"email": payload["email"], "password": payload["password"]},
    )
    token = login_response.json["auth_token"]
    return created["id"], {"Authorization": f"Bearer {token}"}


def seed_manager(db, **overrides):  # pylint: disable=redefined-outer-name
    """Insert a manager account directly into the database, bypassing
    the API -- there is no API route to create the first manager, by
    design (see Mechanic.role in app/models/mechanic.py). Returns
    (manager, plaintext_password) so the caller can log in through
    the real API afterward.

    Defaults to a distinct identity (name/email) from
    make_mechanic_payload()'s default -- otherwise a test that seeds
    a manager and then creates a mechanic via the API with no
    overrides would collide on email and fail with a 400, since both
    would default to the same "Alex Chen" identity.
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
    login_response = client.post(
        "/mechanics/login",
        json={"email": manager_obj.email, "password": password},
    )
    token = login_response.json["auth_token"]
    return manager_obj.id, {"Authorization": f"Bearer {token}"}


def create_mechanic(client, manager_headers, **overrides):
    """Create a regular mechanic through the real API (requires a
    manager token, since mechanic creation is manager-only), then log
    them in. Returns (mechanic_id, auth_headers)."""
    payload = make_mechanic_payload(**overrides)
    created = client.post("/mechanics", json=payload, headers=manager_headers).json
    login_response = client.post(
        "/mechanics/login",
        json={"email": payload["email"], "password": payload["password"]},
    )
    token = login_response.json["auth_token"]
    return created["id"], {"Authorization": f"Bearer {token}"}


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
