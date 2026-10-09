"""
Configuration classes for the Flask app.

Three configs are defined:
- DevelopmentConfig: connects to the real MySQL database, using
  credentials pulled from environment variables (via a local .env
  file) so nothing sensitive is hardcoded or committed to git.
- TestingConfig: uses an in-memory SQLite database instead of MySQL.
  This keeps the test suite fast, isolated from the real database, and
  runnable without a MySQL server available at all (useful for CI,
  where spinning up MySQL is extra setup we don't need for model-level
  tests). It also switches off rate limiting and caching so existing
  tests never hit a limit or read stale cached data; the tests that
  cover those features opt back in with their own subclasses.
- ProductionConfig: connects to the live PostgreSQL database hosted
  on Render, using credentials Render injects as real environment
  variables (not a .env file -- see flask_app.py). Debug mode is
  explicitly off, since Flask's debugger leaks stack traces and
  allows arbitrary code execution if ever exposed on a live server.
"""

import os
from dotenv import load_dotenv

# Loads variables from a local .env file into the environment. Must
# run before os.getenv() calls below, or they'll return None. Has no
# effect in production: Render sets real environment variables
# directly, and there is no .env file deployed alongside the app.
load_dotenv()


class Config:
    """Shared base config. Subclasses override what differs."""

    SQLALCHEMY_TRACK_MODIFICATIONS = False

    # Signs and verifies JWTs (see app/utils/util.py). Sourced from
    # .env locally, or a real environment variable in production, so
    # the real key is never committed to source control either way.
    SECRET_KEY = os.getenv("SECRET_KEY")

    # Flask-Caching: in-process memory cache. Simple and dependency-free,
    # but each process has its own cache and it empties on restart; a
    # multi-server production deployment would use Redis instead.
    CACHE_TYPE = "SimpleCache"
    CACHE_DEFAULT_TIMEOUT = 60  # seconds, used when a route sets no timeout

    # Flask-Limiter: keep request counters in memory (also per-process,
    # also reset on restart). Setting this explicitly silences the
    # "in-memory storage" warning Flask-Limiter prints otherwise.
    RATELIMIT_STORAGE_URI = "memory://"
    # Adds X-RateLimit-Limit / -Remaining / -Reset headers to responses,
    # which makes rate limiting easy to see in Postman's Headers tab.
    RATELIMIT_HEADERS_ENABLED = True


class DevelopmentConfig(Config):
    """Connects to the real MySQL database for local development."""

    _db_user = os.getenv("DB_USER")
    _db_password = os.getenv("DB_PASSWORD")
    _db_host = os.getenv("DB_HOST")
    _db_name = os.getenv("DB_NAME")

    SQLALCHEMY_DATABASE_URI = (
        f"mysql+mysqlconnector://{_db_user}:{_db_password}@{_db_host}/{_db_name}"
    )


class TestingConfig(Config):
    """In-memory SQLite for fast, isolated test runs."""

    TESTING = True
    SQLALCHEMY_DATABASE_URI = "sqlite:///:memory:"

    # Fixed rather than inherited from .env -- tests must never depend
    # on a real secret existing, especially in CI, which has no .env.
    SECRET_KEY = "testing-secret-key"

    # NullCache stores nothing, so every request hits the database and
    # tests never see stale cached data.
    CACHE_TYPE = "NullCache"
    # NullCache is deliberate here, so silence Flask-Caching's warning
    # about it (otherwise it prints once per test-app creation).
    CACHE_NO_NULL_WARNING = True
    # Without this, the suite's many POSTs from one test-client IP would
    # trip the customer-creation limit partway through.
    RATELIMIT_ENABLED = False


class ProductionConfig(Config):
    """Connects to the live PostgreSQL database hosted on Render.

    DEBUG is explicitly False (Flask already defaults to this, but
    stating it here makes the intent unmissable on a config used for
    a publicly reachable server) -- debug mode's interactive debugger
    allows arbitrary Python execution from the browser if a request
    ever triggers an unhandled exception, which is a real security
    hole on anything other than localhost.

    SQLALCHEMY_DATABASE_URI is read directly from the
    SQLALCHEMY_DATABASE_URI environment variable (Render's own
    External Database URL for the Postgres instance, pasted into
    Render's dashboard as a real environment variable during Web
    Service setup) rather than built from separate host/user/password
    pieces the way DevelopmentConfig is -- Render provides the whole
    URI as one value, already in the right format for SQLAlchemy.
    """

    DEBUG = False
    SQLALCHEMY_DATABASE_URI = os.getenv("SQLALCHEMY_DATABASE_URI")
