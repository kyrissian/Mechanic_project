"""
Unittest-style tests for the Service Ticket blueprint.

See test_customers.py's module docstring for why this file exists
alongside the pytest suite: this one satisfies the assignment's
literal unittest/discover requirement; the pytest suite remains the
exhaustive day-to-day coverage.

make_ticket_payload is imported from the pytest suite's own
test_service_ticket_routes.py rather than redefined here -- the two
were identical, which Pylint's duplicate-code check (correctly)
flagged.
"""

from app.extensions import db
from tests.conftest import create_manager, create_mechanic, create_ticket, make_customer_payload
from tests.test_service_ticket_routes import make_ticket_payload
from tests.unittest_suite.base import APITestCase


# pylint: disable=too-many-public-methods
# This class holds 20 test methods, one per route/case, matching the
# assignment's one-file-per-blueprint structure; splitting it into
# multiple classes purely to satisfy Pylint's default method-count
# cap would make the file harder to navigate, not easier -- a normal
# tradeoff for test classes, which is why this check is commonly
# disabled for them rather than restructured around.
class TestServiceTickets(APITestCase):
    """At least one success case and one failure case per
    /service-tickets route, per the assignment rubric."""

    # POST /service-tickets
    def test_create_ticket_as_manager(self):
        """POST /service-tickets should succeed when authenticated as a manager."""
        _, manager_headers = create_manager(self.client, db)
        customer_id = self.client.post('/customers', json=make_customer_payload()).json['id']
        response = self.client.post(
            '/service-tickets', json=make_ticket_payload(customer_id), headers=manager_headers
        )
        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.json['status'], 'Pending')

    def test_create_ticket_as_regular_mechanic(self):
        """POST /service-tickets should return 403 for a non-manager mechanic."""
        _, manager_headers = create_manager(self.client, db)
        _, mechanic_headers = create_mechanic(self.client, manager_headers)
        customer_id = self.client.post('/customers', json=make_customer_payload()).json['id']
        response = self.client.post(
            '/service-tickets', json=make_ticket_payload(customer_id), headers=mechanic_headers
        )
        self.assertEqual(response.status_code, 403)

    # GET /service-tickets
    def test_get_service_tickets(self):
        """GET /service-tickets should return a paginated list for any mechanic."""
        _, manager_headers = create_manager(self.client, db)
        create_ticket(self.client, manager_headers)
        response = self.client.get('/service-tickets', headers=manager_headers)
        self.assertEqual(response.status_code, 200)
        self.assertIn('tickets', response.json)

    def test_get_service_tickets_no_token(self):
        """GET /service-tickets should return 401 with no Authorization header."""
        response = self.client.get('/service-tickets')
        self.assertEqual(response.status_code, 401)

    # GET /service-tickets/my-tickets
    def test_get_my_assigned_tickets(self):
        """GET /service-tickets/my-tickets should return tickets
        assigned to the logged-in mechanic."""
        _, manager_headers = create_manager(self.client, db)
        mechanic_id, mechanic_headers = create_mechanic(self.client, manager_headers)
        ticket_id = create_ticket(self.client, manager_headers)
        self.client.put(
            f'/service-tickets/{ticket_id}/assign-mechanic/{mechanic_id}',
            headers=manager_headers,
        )
        response = self.client.get('/service-tickets/my-tickets', headers=mechanic_headers)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json['total'], 1)

    def test_get_my_assigned_tickets_no_token(self):
        """GET /service-tickets/my-tickets should return 401 with no Authorization header."""
        response = self.client.get('/service-tickets/my-tickets')
        self.assertEqual(response.status_code, 401)

    # GET /service-tickets/<id>
    def test_get_single_ticket(self):
        """GET /service-tickets/<id> should return that ticket's details."""
        _, manager_headers = create_manager(self.client, db)
        ticket_id = create_ticket(self.client, manager_headers)
        response = self.client.get(f'/service-tickets/{ticket_id}', headers=manager_headers)
        self.assertEqual(response.status_code, 200)

    def test_get_single_ticket_not_found(self):
        """GET /service-tickets/<id> should return 404 for an id that doesn't exist."""
        _, manager_headers = create_manager(self.client, db)
        response = self.client.get('/service-tickets/999', headers=manager_headers)
        self.assertEqual(response.status_code, 404)

    # PUT /service-tickets/<id>
    def test_update_ticket_details(self):
        """PUT /service-tickets/<id> should update cost/description for a manager."""
        _, manager_headers = create_manager(self.client, db)
        ticket_id = create_ticket(self.client, manager_headers)
        response = self.client.put(
            f'/service-tickets/{ticket_id}', json={"cost": "500.00"}, headers=manager_headers
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json['cost'], '500.00')

    def test_update_ticket_details_empty_body(self):
        """PUT /service-tickets/<id> should return 400 when neither field is provided."""
        _, manager_headers = create_manager(self.client, db)
        ticket_id = create_ticket(self.client, manager_headers)
        response = self.client.put(
            f'/service-tickets/{ticket_id}', json={}, headers=manager_headers
        )
        self.assertEqual(response.status_code, 400)

    # PUT /service-tickets/<id>/status
    def test_update_ticket_status_as_assigned_mechanic(self):
        """PUT /service-tickets/<id>/status should succeed for an assigned mechanic."""
        _, manager_headers = create_manager(self.client, db)
        mechanic_id, mechanic_headers = create_mechanic(self.client, manager_headers)
        ticket_id = create_ticket(self.client, manager_headers)
        self.client.put(
            f'/service-tickets/{ticket_id}/assign-mechanic/{mechanic_id}',
            headers=manager_headers,
        )
        response = self.client.put(
            f'/service-tickets/{ticket_id}/status',
            json={"status": "In Progress"},
            headers=mechanic_headers,
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json['status'], 'In Progress')

    def test_update_ticket_status_as_unassigned_mechanic(self):
        """PUT /service-tickets/<id>/status should return 403 for an unassigned mechanic."""
        _, manager_headers = create_manager(self.client, db)
        _, mechanic_headers = create_mechanic(self.client, manager_headers)
        ticket_id = create_ticket(self.client, manager_headers)
        response = self.client.put(
            f'/service-tickets/{ticket_id}/status',
            json={"status": "In Progress"},
            headers=mechanic_headers,
        )
        self.assertEqual(response.status_code, 403)

    # PUT /service-tickets/<id>/assign-mechanic/<id>
    def test_assign_mechanic_to_ticket(self):
        """PUT /service-tickets/<id>/assign-mechanic/<id> should add the mechanic to the ticket."""
        _, manager_headers = create_manager(self.client, db)
        mechanic_id, _ = create_mechanic(self.client, manager_headers)
        ticket_id = create_ticket(self.client, manager_headers)
        response = self.client.put(
            f'/service-tickets/{ticket_id}/assign-mechanic/{mechanic_id}',
            headers=manager_headers,
        )
        self.assertEqual(response.status_code, 200)
        self.assertIn(mechanic_id, response.json['mechanic_ids'])

    def test_assign_mechanic_duplicate(self):
        """PUT /service-tickets/<id>/assign-mechanic/<id> should
        return 400 for a duplicate assignment."""
        _, manager_headers = create_manager(self.client, db)
        mechanic_id, _ = create_mechanic(self.client, manager_headers)
        ticket_id = create_ticket(self.client, manager_headers)
        self.client.put(
            f'/service-tickets/{ticket_id}/assign-mechanic/{mechanic_id}',
            headers=manager_headers,
        )
        response = self.client.put(
            f'/service-tickets/{ticket_id}/assign-mechanic/{mechanic_id}',
            headers=manager_headers,
        )
        self.assertEqual(response.status_code, 400)

    # PUT /service-tickets/<id>/remove-mechanic/<id>
    def test_remove_mechanic_from_ticket(self):
        """PUT /service-tickets/<id>/remove-mechanic/<id> should remove an assigned mechanic."""
        _, manager_headers = create_manager(self.client, db)
        mechanic_id, _ = create_mechanic(self.client, manager_headers)
        ticket_id = create_ticket(self.client, manager_headers)
        self.client.put(
            f'/service-tickets/{ticket_id}/assign-mechanic/{mechanic_id}',
            headers=manager_headers,
        )
        response = self.client.put(
            f'/service-tickets/{ticket_id}/remove-mechanic/{mechanic_id}',
            headers=manager_headers,
        )
        self.assertEqual(response.status_code, 200)
        self.assertNotIn(mechanic_id, response.json['mechanic_ids'])

    def test_remove_mechanic_not_assigned(self):
        """PUT /service-tickets/<id>/remove-mechanic/<id> should return 400 if not assigned."""
        _, manager_headers = create_manager(self.client, db)
        mechanic_id, _ = create_mechanic(self.client, manager_headers)
        ticket_id = create_ticket(self.client, manager_headers)
        response = self.client.put(
            f'/service-tickets/{ticket_id}/remove-mechanic/{mechanic_id}',
            headers=manager_headers,
        )
        self.assertEqual(response.status_code, 400)

    # PUT /service-tickets/<id>/edit
    def test_bulk_edit_ticket_mechanics(self):
        """PUT /service-tickets/<id>/edit should bulk add/remove mechanics."""
        _, manager_headers = create_manager(self.client, db)
        mechanic_id, _ = create_mechanic(self.client, manager_headers)
        ticket_id = create_ticket(self.client, manager_headers)
        response = self.client.put(
            f'/service-tickets/{ticket_id}/edit',
            json={"add_ids": [mechanic_id], "remove_ids": []},
            headers=manager_headers,
        )
        self.assertEqual(response.status_code, 200)
        self.assertIn(mechanic_id, response.json['mechanic_ids'])

    def test_bulk_edit_nonexistent_mechanic(self):
        """PUT /service-tickets/<id>/edit should return 404 for a nonexistent mechanic id."""
        _, manager_headers = create_manager(self.client, db)
        ticket_id = create_ticket(self.client, manager_headers)
        response = self.client.put(
            f'/service-tickets/{ticket_id}/edit',
            json={"add_ids": [999999], "remove_ids": []},
            headers=manager_headers,
        )
        self.assertEqual(response.status_code, 404)

    # PUT /service-tickets/<id>/add-part/<id>
    def test_add_part_to_ticket(self):
        """PUT /service-tickets/<id>/add-part/<id> should add a part and decrement stock."""
        _, manager_headers = create_manager(self.client, db)
        ticket_id = create_ticket(self.client, manager_headers)
        part_id = self.client.post(
            '/inventory',
            json={"name": "Oil Filter", "price": "12.50", "quantity_on_hand": 20},
            headers=manager_headers,
        ).json['id']
        response = self.client.put(
            f'/service-tickets/{ticket_id}/add-part/{part_id}', headers=manager_headers
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.json['parts']), 1)

    def test_add_part_exceeds_stock(self):
        """PUT /service-tickets/<id>/add-part/<id> should return 400 when over-allocating stock."""
        _, manager_headers = create_manager(self.client, db)
        ticket_id = create_ticket(self.client, manager_headers)
        part_id = self.client.post(
            '/inventory',
            json={"name": "Brake Rotor", "price": "74.50", "quantity_on_hand": 2},
            headers=manager_headers,
        ).json['id']
        response = self.client.put(
            f'/service-tickets/{ticket_id}/add-part/{part_id}',
            json={"quantity": 5},
            headers=manager_headers,
        )
        self.assertEqual(response.status_code, 400)
