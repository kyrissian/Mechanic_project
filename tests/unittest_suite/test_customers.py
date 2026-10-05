"""
Unittest-style tests for the Customer blueprint.

Written specifically to satisfy this assignment's rubric: unittest
(not pytest), one file per blueprint, run via
`python -m unittest discover tests`. The existing pytest suite in
this same tests/ folder remains the primary, exhaustive test suite
(173 tests, run via `pytest`) -- pytest-style function tests are
invisible to unittest's own discovery, which only finds
unittest.TestCase subclasses, so this file exists to make the
assignment's literal run command actually find and run real tests.

Reuses the plain-function helpers already in conftest.py
(make_customer_payload, login_customer, create_manager, etc.) rather
than re-implementing the same setup logic in a second style -- those
helpers were never pytest-specific; they just take client/db as
arguments, so they work identically here.
"""

import unittest

from app import create_app
from app.extensions import db
from config import TestingConfig
from tests.conftest import (
    create_manager,
    create_ticket,
    login_customer,
    make_customer_payload,
)


class TestCustomers(unittest.TestCase):
    """At least one success case and one failure case per /customers
    route, per the assignment rubric."""

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

    # POST /customers
    def test_create_customer(self):
        """POST /customers should create a customer and return 201."""
        response = self.client.post('/customers', json=make_customer_payload())
        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.json['email'], 'jamie@example.com')

    def test_create_customer_missing_field(self):
        """POST /customers should return 400 when a required field is missing."""
        response = self.client.post('/customers', json={"name": "Jamie"})
        self.assertEqual(response.status_code, 400)
        self.assertIn('email', response.json['details'])

    # POST /customers/login
    def test_login_customer(self):
        """POST /customers/login should return a token for valid credentials."""
        payload = make_customer_payload()
        self.client.post('/customers', json=payload)
        response = self.client.post('/customers/login', json={
            "email": payload["email"], "password": payload["password"]
        })
        self.assertEqual(response.status_code, 200)
        self.assertIn('auth_token', response.json)

    def test_login_customer_wrong_password(self):
        """POST /customers/login should return 401 for a wrong password."""
        payload = make_customer_payload()
        self.client.post('/customers', json=payload)
        response = self.client.post('/customers/login', json={
            "email": payload["email"], "password": "wrong"
        })
        self.assertEqual(response.status_code, 401)

    # GET /customers
    def test_get_customers_as_mechanic(self):
        """GET /customers should succeed for a logged-in mechanic."""
        _, manager_headers = create_manager(self.client, db)
        response = self.client.get('/customers', headers=manager_headers)
        self.assertEqual(response.status_code, 200)
        self.assertIn('customers', response.json)

    def test_get_customers_no_token(self):
        """GET /customers should return 401 with no Authorization header."""
        response = self.client.get('/customers')
        self.assertEqual(response.status_code, 401)

    # GET /customers/<id>
    def test_get_single_customer(self):
        """GET /customers/<id> should return that customer's details."""
        customer_id, _ = login_customer(self.client)
        _, manager_headers = create_manager(self.client, db)
        response = self.client.get(f'/customers/{customer_id}', headers=manager_headers)
        self.assertEqual(response.status_code, 200)

    def test_get_single_customer_not_found(self):
        """GET /customers/<id> should return 404 for an id that doesn't exist."""
        _, manager_headers = create_manager(self.client, db)
        response = self.client.get('/customers/999', headers=manager_headers)
        self.assertEqual(response.status_code, 404)

    # GET /customers/my-tickets
    def test_get_my_tickets(self):
        """GET /customers/my-tickets should return the logged-in customer's tickets."""
        _, headers = login_customer(self.client)
        response = self.client.get('/customers/my-tickets', headers=headers)
        self.assertEqual(response.status_code, 200)
        self.assertIn('tickets', response.json)

    def test_get_my_tickets_no_token(self):
        """GET /customers/my-tickets should return 401 with no Authorization header."""
        response = self.client.get('/customers/my-tickets')
        self.assertEqual(response.status_code, 401)

    # PUT /customers/<id>
    def test_update_customer(self):
        """PUT /customers/<id> should update the logged-in customer's own account."""
        customer_id, headers = login_customer(self.client)
        response = self.client.put(
            f'/customers/{customer_id}',
            json=make_customer_payload(name="Updated Name"),
            headers=headers,
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json['name'], 'Updated Name')

    def test_update_customer_wrong_owner(self):
        """PUT /customers/<id> should return 403 when updating someone else's account."""
        _, headers_a = login_customer(self.client)
        customer_b_id, _ = login_customer(
            self.client, name="Other", email="other@example.com"
        )
        response = self.client.put(
            f'/customers/{customer_b_id}',
            json=make_customer_payload(name="Hacked"),
            headers=headers_a,
        )
        self.assertEqual(response.status_code, 403)

    # DELETE /customers/<id>
    def test_delete_customer_no_history(self):
        """DELETE /customers/<id> should close an account with no service history."""
        customer_id, headers = login_customer(self.client)
        response = self.client.delete(f'/customers/{customer_id}', headers=headers)
        self.assertEqual(response.status_code, 200)

    def test_delete_customer_with_history(self):
        """DELETE /customers/<id> should return 409 for an account with service history."""
        customer_id, headers = login_customer(self.client)
        _, manager_headers = create_manager(self.client, db)
        create_ticket(self.client, manager_headers, customer_id=customer_id)
        response = self.client.delete(f'/customers/{customer_id}', headers=headers)
        self.assertEqual(response.status_code, 409)


if __name__ == '__main__':
    unittest.main()
