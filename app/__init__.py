"""
Application factory.

Using create_app() instead of a module-level `app = Flask(__name__)`
is what makes this project testable: each test run can call
create_app(TestingConfig) to get its own fresh app instance wired to
an isolated in-memory database, without ever touching the real
MySQL database or interfering with a separately-running dev server.
"""

from flask import Flask
from app.extensions import db, ma
from config import DevelopmentConfig


def create_app(config_class=DevelopmentConfig):
    """Build and return a configured Flask app.

    config_class controls which database the app connects to --
    DevelopmentConfig (the real MySQL database) by default, or
    TestingConfig (in-memory SQLite) when called from tests.
    """
    app = Flask(__name__)
    app.config.from_object(config_class)

    db.init_app(app)
    ma.init_app(app)

    # Models must be imported after db.init_app() so SQLAlchemy knows
    # about every table before anything (like db.create_all(), used in
    # tests) tries to create them. service_mechanics must come before
    # mechanic/service_ticket since relationship(secondary=...) in
    # those files refers to it by table name. These imports are for
    # their side effect (registering each model's table with
    # SQLAlchemy) rather than to use the names directly, hence the
    # disable comment below.
    # pylint: disable=unused-import,import-outside-toplevel

    from app.models import customer, service_mechanics, mechanic, service_ticket

    from app.blueprints.customer import customer_bp
    app.register_blueprint(customer_bp)

    return app
