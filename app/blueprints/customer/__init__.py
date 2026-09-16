"""
Initializes the Customer blueprint.

The Blueprint object is created here rather than in routes.py, so
routes.py can import it without owning it -- and this file imports
routes.py at the very bottom (after customer_bp already exists) so
every @customer_bp.route decorator in routes.py actually attaches to
this blueprint. That ordering is what avoids a circular import
between this file and routes.py.
"""

from flask import Blueprint

customer_bp = Blueprint("customers", __name__)

# Imported for its side effect: running routes.py registers every
# @customer_bp.route(...) decorated function onto customer_bp above.
# Must stay at the bottom, after customer_bp is defined.
from app.blueprints.customer import routes  # noqa: E402,F401  pylint: disable=wrong-import-position,unused-import
