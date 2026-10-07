"""
Shared base TestCase for the unittest suite.

Every blueprint's test file (test_customers.py, test_mechanics.py,
test_service_tickets.py, test_inventory.py) previously duplicated the
exact same setUp/tearDown block -- flagged by Pylint's duplicate-code
check (R0801) across all four files. Factoring it into one base class
here removes that duplication at the source rather than suppressing
the warning.
"""

import unittest

from app import create_app
from app.extensions import db
from config import TestingConfig


class APITestCase(unittest.TestCase):
    """Base class providing a fresh app, in-memory database, and test
    client before each test, torn down after. Every TestCase in this
    suite subclasses this instead of unittest.TestCase directly."""

    def setUp(self):
        """Build a fresh app and in-memory database before each test."""
        self.app = create_app(TestingConfig)
        self.app_context = self.app.app_context()
        self.app_context.push()
        db.drop_all()
        db.create_all()
        self.client = self.app.test_client()

    def tearDown(self):
        """Tear down the database and app context after each test."""
        db.session.remove()
        db.drop_all()
        self.app_context.pop()
