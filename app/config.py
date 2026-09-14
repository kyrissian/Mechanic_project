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
  tests).
"""

import os
from dotenv import load_dotenv

# Loads variables from a local .env file into the environment. Must
# run before os.getenv() calls below, or they'll return None.
load_dotenv()


class Config:
    """Shared base config. Subclasses override what differs."""

    SQLALCHEMY_TRACK_MODIFICATIONS = False


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
