"""
Initializes the Mechanic blueprint.

Same pattern as the Customer blueprint: the Blueprint object is
created here, and routes.py is imported at the bottom (after
mechanic_bp already exists) so its route decorators attach correctly
without a circular import.
"""

from flask import Blueprint

mechanic_bp = Blueprint("mechanics", __name__)

# Imported for its side effect: running routes.py registers every
# @mechanic_bp.route(...) decorated function onto mechanic_bp above.
from app.blueprints.mechanic import routes  # noqa: E402,F401  pylint: disable=wrong-import-position,unused-import
