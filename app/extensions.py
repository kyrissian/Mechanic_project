"""
Shared Flask extension instances.

Kept separate from the app factory (app/__init__.py) specifically to
avoid a circular import: model/schema files need to import `db`/`ma`
to define their columns/fields, and the app factory needs to import
the models to register them -- if these lived in app/__init__.py,
those imports would depend on each other.

This module also holds the rate limiter and cache instances. Like `db`
and `ma`, they are created here without an app and bound to it later by
`init_app()` inside the factory, so routes can import them without
importing the app itself.
"""

import sqlite3

from flask_caching import Cache
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
from flask_sqlalchemy import SQLAlchemy
from flask_marshmallow import Marshmallow
from sqlalchemy import event
from sqlalchemy.engine import Engine

db = SQLAlchemy()
ma = Marshmallow()

# Rate limiter: identifies each client by IP address so limits apply per
# client. default_limits is a floor applied to EVERY route automatically,
# including ones with no @limiter.limit of their own -- a backstop against
# scraping or a runaway client loop on routes we never thought to protect
# individually. Routes with their own @limiter.limit (create_customer,
# create_mechanic, the delete routes) are always stricter than this floor,
# so both limits are tracked but the tighter one is always what triggers.
limiter = Limiter(
    key_func=get_remote_address,
    default_limits=["200 per day", "50 per hour"],
)

# Cache: intentionally created with no config. The backend (SimpleCache in
# development, NullCache in tests) comes from config.py, because config
# passed to the Cache() constructor would override app.config and make it
# impossible to turn caching off for tests.
cache = Cache()


@event.listens_for(Engine, "connect")
def _enable_sqlite_foreign_keys(dbapi_connection, _connection_record):
    """SQLite does not enforce foreign key constraints by default,
    unlike MySQL -- meaning a bug that creates a row with an invalid
    foreign key (e.g. a ServiceTicket pointing at a customer_id that
    doesn't exist) would silently succeed in our test database even
    though the real MySQL database would reject it. This turns FK
    enforcement on for SQLite connections specifically, so our tests
    see the same behavior as production. Guarded with an isinstance
    check so this never runs against a real MySQL connection, which
    has no concept of SQLite's PRAGMA syntax.
    """
    if isinstance(dbapi_connection, sqlite3.Connection):
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()
