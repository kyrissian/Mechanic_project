"""
Initializes the Inventory blueprint.
"""

from flask import Blueprint

inventory_bp = Blueprint("inventory", __name__)

from app.blueprints.inventory import routes  # noqa: E402,F401  pylint: disable=wrong-import-position,unused-import
