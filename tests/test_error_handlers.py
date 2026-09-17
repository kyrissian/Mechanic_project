"""Tests for the global error handlers -- confirming every kind of
HTTP error returns consistent JSON, not Flask's default HTML pages."""


def test_unmatched_route_returns_json_404(client):
    """A URL that matches no route at all should return JSON, not
    Flask's default HTML 404 page."""
    response = client.get("/this-route-does-not-exist")

    assert response.status_code == 404
    assert response.content_type == "application/json"
    assert "error" in response.json


def test_wrong_method_returns_json_405(client):
    """Using an HTTP method a route doesn't support should return
    JSON, not an HTML 405 page. /customers/<id> supports GET/PUT/
    DELETE, not POST."""
    response = client.post("/customers/1")

    assert response.status_code == 405
    assert response.content_type == "application/json"
    assert "error" in response.json


def test_malformed_json_body_returns_json_400(client):
    """Sending a body that isn't valid JSON should return a clean
    JSON 400, not Flask's raw parsing error as HTML."""
    response = client.post(
        "/customers",
        data="{not valid json",
        content_type="application/json",
    )

    assert response.status_code == 400
    assert response.content_type == "application/json"
    assert "error" in response.json


def test_missing_content_type_returns_json_415(client):
    """Sending a JSON-shaped body without the application/json
    Content-Type header should return a clean JSON 415, not an HTML
    page. 415 (not 400) is the correct status here -- Flask
    recognizes the Content-Type itself as the problem, distinct from
    a 400 for genuinely malformed JSON syntax."""
    response = client.post(
        "/customers",
        data='{"name": "Jamie Rivera", "email": "jamie@example.com", "phone": "555-123-4567"}',
        content_type="text/plain",
    )

    assert response.status_code == 415
    assert response.content_type == "application/json"
    assert "error" in response.json
