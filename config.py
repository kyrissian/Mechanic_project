"""
Configuration classes for the Flask app.

Two configs are defined:
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
"""

import os
from dotenv import load_dotenv

# Loads variables from a local .env file into the environment. Must
# run before os.getenv() calls below, or they'll return None.
load_dotenv()


class Config:
    """Shared base config. Subclasses override what differs."""

    SQLALCHEMY_TRACK_MODIFICATIONS = False

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

    # NullCache stores nothing, so every request hits the database and
    # tests never see stale cached data.
    CACHE_TYPE = "NullCache"
    # NullCache is deliberate here, so silence Flask-Caching's warning
    # about it (otherwise it prints once per test-app creation).
    CACHE_NO_NULL_WARNING = True
    # Without this, the suite's many POSTs from one test-client IP would
    # trip the customer-creation limit partway through.
    RATELIMIT_ENABLED = False
