"""
Application factory.

Using create_app() instead of a module-level `app = Flask(__name__)`
is what makes this project testable: each test run can call
create_app(TestingConfig) to get its own fresh app instance wired to
an isolated in-memory database, without ever touching the real
MySQL database or interfering with a separately-running dev server.
"""

from flask import Flask
from flask_swagger_ui import get_swaggerui_blueprint

from app.extensions import cache, db, limiter, ma
from app.logging_config import configure_logging
from config import DevelopmentConfig

SWAGGER_URL = "/api/docs"
API_URL = "/static/swagger.yaml"

swaggerui_blueprint = get_swaggerui_blueprint(
    SWAGGER_URL,
    API_URL,
    config={"app_name": "Mechanic Shop API", "persistAuthorization": True},
)


def create_app(config_class=DevelopmentConfig):
    """Build and return a configured Flask app.

    config_class controls which database the app connects to --
    DevelopmentConfig (the real MySQL database) by default, or
    TestingConfig (in-memory SQLite) when called from tests. It also
    controls whether rate limiting and caching are active, since
    TestingConfig turns both off.
    """
    app = Flask(__name__)
    app.config.from_object(config_class)

    # Configured before any extension or blueprint below so that
    # everything -- including a logging call made during their own
    # setup -- goes through the same request-ID-tagged formatter.
    configure_logging(app)

    db.init_app(app)
    ma.init_app(app)
    limiter.init_app(app)
    cache.init_app(app)

    from app.error_handlers import register_error_handlers  # pylint: disable=import-outside-toplevel
    register_error_handlers(app)

    # pylint: disable=unused-import,import-outside-toplevel
    from app.models import (
        customer,
        service_mechanics,
        mechanic,
        service_ticket,
        inventory,
        ticket_part,
    )

    from app.blueprints.customer import customer_bp
    app.register_blueprint(customer_bp, url_prefix="/customers")

    from app.blueprints.mechanic import mechanic_bp
    app.register_blueprint(mechanic_bp, url_prefix="/mechanics")

    from app.blueprints.service_ticket import service_ticket_bp
    app.register_blueprint(service_ticket_bp, url_prefix="/service-tickets")

    from app.blueprints.inventory import inventory_bp
    app.register_blueprint(inventory_bp, url_prefix="/inventory")

    # No url_prefix: GET /health is meant to be a short, memorable path
    # for an external uptime monitor to poll, not nested under any
    # resource prefix.
    from app.blueprints.health import health_bp
    app.register_blueprint(health_bp)

    app.register_blueprint(swaggerui_blueprint, url_prefix=SWAGGER_URL)

    return app
