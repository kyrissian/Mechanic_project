"""
Unittest-style tests for the Mechanic blueprint.

See test_customers.py's module docstring for why this file exists
alongside the pytest suite: this one satisfies the assignment's
literal unittest/discover requirement; the pytest suite remains the
exhaustive day-to-day coverage.
"""

from app.extensions import db
from tests.conftest import create_manager, create_mechanic, make_mechanic_payload
from tests.unittest_suite.base import APITestCase


class TestMechanics(APITestCase):
    """At least one success case and one failure case per /mechanics
    route, per the assignment rubric."""

    # POST /mechanics
    def test_create_mechanic_as_manager(self):
        """POST /mechanics should succeed when authenticated as a manager."""
        _, manager_headers = create_manager(self.client, db)
        response = self.client.post(
            '/mechanics', json=make_mechanic_payload(), headers=manager_headers
        )
        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.json['role'], 'mechanic')

    def test_create_mechanic_as_regular_mechanic(self):
        """POST /mechanics should return 403 for a non-manager mechanic."""
        _, manager_headers = create_manager(self.client, db)
        _, mechanic_headers = create_mechanic(self.client, manager_headers)
        response = self.client.post(
            '/mechanics', json=make_mechanic_payload(index=2), headers=mechanic_headers
        )
        self.assertEqual(response.status_code, 403)

    # POST /mechanics/login
    def test_login_mechanic(self):
        """POST /mechanics/login should return a token for valid credentials."""
        _, manager_headers = create_manager(self.client, db)
        payload = make_mechanic_payload()
        self.client.post('/mechanics', json=payload, headers=manager_headers)
        response = self.client.post('/mechanics/login', json={
            "email": payload["email"], "password": payload["password"]
        })
        self.assertEqual(response.status_code, 200)
        self.assertIn('auth_token', response.json)

    def test_login_mechanic_wrong_password(self):
        """POST /mechanics/login should return 401 for invalid credentials."""
        response = self.client.post('/mechanics/login', json={
            "email": "nobody@example.com", "password": "wrong"
        })
        self.assertEqual(response.status_code, 401)

    # GET /mechanics
    def test_get_mechanics_as_manager(self):
        """GET /mechanics should succeed for a manager, returning the full roster."""
        _, manager_headers = create_manager(self.client, db)
        response = self.client.get('/mechanics', headers=manager_headers)
        self.assertEqual(response.status_code, 200)
        self.assertIn('mechanics', response.json)

    def test_get_mechanics_as_regular_mechanic(self):
        """GET /mechanics should return 403 for a non-manager mechanic."""
        _, manager_headers = create_manager(self.client, db)
        _, mechanic_headers = create_mechanic(self.client, manager_headers)
        response = self.client.get('/mechanics', headers=mechanic_headers)
        self.assertEqual(response.status_code, 403)

    # GET /mechanics/most-tickets
    def test_get_mechanics_most_tickets(self):
        """GET /mechanics/most-tickets should return a sorted list for any mechanic."""
        _, manager_headers = create_manager(self.client, db)
        response = self.client.get('/mechanics/most-tickets', headers=manager_headers)
        self.assertEqual(response.status_code, 200)
        self.assertIsInstance(response.json, list)

    def test_get_mechanics_most_tickets_no_token(self):
        """GET /mechanics/most-tickets should return 401 with no Authorization header."""
        response = self.client.get('/mechanics/most-tickets')
        self.assertEqual(response.status_code, 401)

    # GET /mechanics/open-tickets
    def test_get_mechanics_open_tickets(self):
        """GET /mechanics/open-tickets should succeed for any logged-in mechanic."""
        _, manager_headers = create_manager(self.client, db)
        response = self.client.get('/mechanics/open-tickets', headers=manager_headers)
        self.assertEqual(response.status_code, 200)

    def test_get_mechanics_open_tickets_no_token(self):
        """GET /mechanics/open-tickets should return 401 with no Authorization header."""
        response = self.client.get('/mechanics/open-tickets')
        self.assertEqual(response.status_code, 401)

    # GET /mechanics/closed-tickets
    def test_get_mechanics_closed_tickets(self):
        """GET /mechanics/closed-tickets should succeed for any logged-in mechanic."""
        _, manager_headers = create_manager(self.client, db)
        response = self.client.get('/mechanics/closed-tickets', headers=manager_headers)
        self.assertEqual(response.status_code, 200)

    def test_get_mechanics_closed_tickets_no_token(self):
        """GET /mechanics/closed-tickets should return 401 with no Authorization header."""
        response = self.client.get('/mechanics/closed-tickets')
        self.assertEqual(response.status_code, 401)

    # GET /mechanics/<id>
    def test_get_own_mechanic_profile(self):
        """GET /mechanics/<id> should return a mechanic's own profile, including salary."""
        _, manager_headers = create_manager(self.client, db)
        mechanic_id, mechanic_headers = create_mechanic(self.client, manager_headers)
        response = self.client.get(f'/mechanics/{mechanic_id}', headers=mechanic_headers)
        self.assertEqual(response.status_code, 200)
        self.assertIn('salary', response.json)

    def test_get_other_mechanic_profile_forbidden(self):
        """GET /mechanics/<id> should return 403 for a non-manager
        viewing someone else's profile."""
        _, manager_headers = create_manager(self.client, db)
        other_id, _ = create_mechanic(self.client, manager_headers, index=2)
        _, mechanic_headers = create_mechanic(self.client, manager_headers, index=3)
        response = self.client.get(f'/mechanics/{other_id}', headers=mechanic_headers)
        self.assertEqual(response.status_code, 403)

    # PUT /mechanics/<id>
    def test_update_mechanic_as_manager(self):
        """PUT /mechanics/<id> should succeed for a manager."""
        _, manager_headers = create_manager(self.client, db)
        mechanic_id, _ = create_mechanic(self.client, manager_headers)
        response = self.client.put(
            f'/mechanics/{mechanic_id}',
            json=make_mechanic_payload(salary=60000.00),
            headers=manager_headers,
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json['salary'], '60000.00')

    def test_update_mechanic_as_regular_mechanic(self):
        """PUT /mechanics/<id> should return 403 for a non-manager mechanic."""
        _, manager_headers = create_manager(self.client, db)
        mechanic_id, mechanic_headers = create_mechanic(self.client, manager_headers)
        response = self.client.put(
            f'/mechanics/{mechanic_id}',
            json=make_mechanic_payload(salary=99999.00),
            headers=mechanic_headers,
        )
        self.assertEqual(response.status_code, 403)

    # DELETE /mechanics/<id>
    def test_delete_mechanic_as_manager(self):
        """DELETE /mechanics/<id> should succeed for a manager."""
        _, manager_headers = create_manager(self.client, db)
        mechanic_id, _ = create_mechanic(self.client, manager_headers)
        response = self.client.delete(f'/mechanics/{mechanic_id}', headers=manager_headers)
        self.assertEqual(response.status_code, 200)

    def test_delete_mechanic_not_found(self):
        """DELETE /mechanics/<id> should return 404 for an id that doesn't exist."""
        _, manager_headers = create_manager(self.client, db)
        response = self.client.delete('/mechanics/999', headers=manager_headers)
        self.assertEqual(response.status_code, 404)
