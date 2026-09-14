"""
Shared Flask extension instances.

Kept separate from the app factory (app/__init__.py) specifically to
avoid a circular import: model files need to import `db` to define
their columns, and the app factory needs to import the models to
register them -- if `db` lived inside app/__init__.py, those two
imports would depend on each other and fail.
"""

from flask_sqlalchemy import SQLAlchemy

db = SQLAlchemy()
