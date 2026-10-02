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
from config import DevelopmentConfig

# URL where the interactive Swagger UI page itself is served, and the
# path to the raw OpenAPI/Swagger spec it reads from -- app/static/
# is served automatically by Flask, so /static/swagger.yaml just
# works without any extra route needed.
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

    db.init_app(app)
    ma.init_app(app)
    limiter.init_app(app)
    cache.init_app(app)

    # Deferred import: avoids a circular dependency, since
    # error_handlers.py doesn't need anything from this module.
    from app.error_handlers import register_error_handlers  # pylint: disable=import-outside-toplevel
    register_error_handlers(app)

    # Models must be imported after db.init_app() so SQLAlchemy knows
    # about every table before anything (like db.create_all(), used in
    # tests) tries to create them. service_mechanics must come before
    # mechanic/service_ticket since relationship(secondary=...) in
    # those files refers to it by table name. inventory and
    # ticket_part come last: ticket_part's foreign keys point at both
    # service_tickets and inventory. These imports are for their side
    # effect (registering each model's table with SQLAlchemy) rather
    # than to use the names directly, hence the disable comment below.
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

    # Serves the interactive Swagger UI at /api/docs, reading its spec
    # from app/static/swagger.yaml (see SWAGGER_URL/API_URL above).
    # Registered last and separately from the resource blueprints
    # above -- it's documentation, not an API resource, and carries no
    # url_prefix of its own since get_swaggerui_blueprint already
    # mounts it at SWAGGER_URL internally.
    app.register_blueprint(swaggerui_blueprint, url_prefix=SWAGGER_URL)

    return app
