"""
Shared Flask extension instances.

Kept separate from the app factory (app/__init__.py) specifically to
avoid a circular import: model/schema files need to import `db`/`ma`
to define their columns/fields, and the app factory needs to import
the models to register them -- if these lived in app/__init__.py,
those imports would depend on each other.
"""

import sqlite3

from flask_sqlalchemy import SQLAlchemy
from flask_marshmallow import Marshmallow
from sqlalchemy import event
from sqlalchemy.engine import Engine

db = SQLAlchemy()
ma = Marshmallow()


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
