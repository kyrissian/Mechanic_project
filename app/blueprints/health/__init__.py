"""
Initializes the Health blueprint.
"""

from flask import Blueprint

health_bp = Blueprint("health", __name__)

from app.blueprints.health import routes  # noqa: E402,F401  pylint: disable=wrong-import-position,unused-import
