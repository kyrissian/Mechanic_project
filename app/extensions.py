"""
Shared Flask extension instances.

Kept separate from the app factory (app/__init__.py) specifically to
avoid a circular import: model/schema files need to import `db`/`ma`
to define their columns/fields, and the app factory needs to import
the models to register them -- if these lived in app/__init__.py,
those imports would depend on each other.
"""

from flask_sqlalchemy import SQLAlchemy
from flask_marshmallow import Marshmallow

db = SQLAlchemy()
ma = Marshmallow()
