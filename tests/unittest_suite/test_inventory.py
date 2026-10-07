"""
Unittest-style tests for the Inventory blueprint.

See test_customers.py's module docstring for why this file exists
alongside the pytest suite: this one satisfies the assignment's
literal unittest/discover requirement; the pytest suite remains the
exhaustive day-to-day coverage.

make_inventory_payload is imported from conftest.py (already used by
the pytest inventory tests) rather than redefined here, for the same
DRY reasoning as test_service_tickets.py importing make_ticket_payload.
"""

from app.extensions import db
from tests.conftest import create_manager, create_mechanic, create_ticket, make_inventory_payload
from tests.unittest_suite.base import APITestCase


class TestInventory(APITestCase):
    """At least one success case and one failure case per /inventory
    route, per the assignment rubric."""

    # POST /inventory
    def test_create_part_as_manager(self):
        """POST /inventory should succeed for a manager."""
        _, manager_headers = create_manager(self.client, db)
        response = self.client.post(
            '/inventory', json=make_inventory_payload(), headers=manager_headers
        )
        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.json['name'], 'Oil Filter')

    def test_create_part_as_regular_mechanic(self):
        """POST /inventory should return 403 for a non-manager mechanic."""
        _, manager_headers = create_manager(self.client, db)
        _, mechanic_headers = create_mechanic(self.client, manager_headers)
        response = self.client.post(
            '/inventory', json=make_inventory_payload(), headers=mechanic_headers
        )
        self.assertEqual(response.status_code, 403)

    # GET /inventory
    def test_get_inventory(self):
        """GET /inventory should return a paginated list for any mechanic."""
        _, manager_headers = create_manager(self.client, db)
        self.client.post('/inventory', json=make_inventory_payload(), headers=manager_headers)
        response = self.client.get('/inventory', headers=manager_headers)
        self.assertEqual(response.status_code, 200)
        self.assertIn('inventory', response.json)

    def test_get_inventory_no_token(self):
        """GET /inventory should return 401 with no Authorization header."""
        response = self.client.get('/inventory')
        self.assertEqual(response.status_code, 401)

    # GET /inventory/<id>
    def test_get_single_part(self):
        """GET /inventory/<id> should return that part's details."""
        _, manager_headers = create_manager(self.client, db)
        part_id = self.client.post(
            '/inventory', json=make_inventory_payload(), headers=manager_headers
        ).json['id']
        response = self.client.get(f'/inventory/{part_id}', headers=manager_headers)
        self.assertEqual(response.status_code, 200)

    def test_get_single_part_not_found(self):
        """GET /inventory/<id> should return 404 for an id that doesn't exist."""
        _, manager_headers = create_manager(self.client, db)
        response = self.client.get('/inventory/999', headers=manager_headers)
        self.assertEqual(response.status_code, 404)

    # PUT /inventory/<id>
    def test_update_part_as_manager(self):
        """PUT /inventory/<id> should update a part for a manager."""
        _, manager_headers = create_manager(self.client, db)
        part_id = self.client.post(
            '/inventory', json=make_inventory_payload(), headers=manager_headers
        ).json['id']
        response = self.client.put(
            f'/inventory/{part_id}',
            json=make_inventory_payload(price="15.00"),
            headers=manager_headers,
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json['price'], '15.00')

    def test_update_part_as_regular_mechanic(self):
        """PUT /inventory/<id> should return 403 for a non-manager mechanic."""
        _, manager_headers = create_manager(self.client, db)
        _, mechanic_headers = create_mechanic(self.client, manager_headers)
        part_id = self.client.post(
            '/inventory', json=make_inventory_payload(), headers=manager_headers
        ).json['id']
        response = self.client.put(
            f'/inventory/{part_id}',
            json=make_inventory_payload(price="1.00"),
            headers=mechanic_headers,
        )
        self.assertEqual(response.status_code, 403)

    # DELETE /inventory/<id>
    def test_delete_unused_part(self):
        """DELETE /inventory/<id> should succeed for a part never used on a ticket."""
        _, manager_headers = create_manager(self.client, db)
        part_id = self.client.post(
            '/inventory', json=make_inventory_payload(), headers=manager_headers
        ).json['id']
        response = self.client.delete(f'/inventory/{part_id}', headers=manager_headers)
        self.assertEqual(response.status_code, 200)

    def test_delete_part_used_on_ticket(self):
        """DELETE /inventory/<id> should return 409 for a part used on a ticket."""
        _, manager_headers = create_manager(self.client, db)
        part_id = self.client.post(
            '/inventory', json=make_inventory_payload(), headers=manager_headers
        ).json['id']
        ticket_id = create_ticket(self.client, manager_headers)
        self.client.put(
            f'/service-tickets/{ticket_id}/add-part/{part_id}', headers=manager_headers
        )
        response = self.client.delete(f'/inventory/{part_id}', headers=manager_headers)
        self.assertEqual(response.status_code, 409)
