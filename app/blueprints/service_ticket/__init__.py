"""
Initializes the ServiceTicket blueprint.
"""

from flask import Blueprint

service_ticket_bp = Blueprint("service_tickets", __name__)

from app.blueprints.service_ticket import routes  # noqa: E402,F401  pylint: disable=wrong-import-position,unused-import
