"""Tests for rate limiting: route-specific limits on customer/mechanic
create and delete, plus the global default applied to every route."""

from tests.conftest import make_customer_payload, make_mechanic_payload


def test_create_customer_blocked_after_five_requests(rate_limited_client):
    """The first five customer creations succeed; the sixth within the
    hour is rejected with a 429 and the JSON body from our handler."""
    for i in range(5):
        response = rate_limited_client.post("/customers", json=make_customer_payload(i))
        assert response.status_code == 201

    response = rate_limited_client.post("/customers", json=make_customer_payload(5))

    assert response.status_code == 429
    assert response.json["error"] == "Rate limit exceeded"
    assert "5 per 1 hour" in response.json["detail"]


def test_rejected_requests_still_count_toward_limit(rate_limited_client):
    """Requests that fail validation (400) still use up the limit, so
    a client can't probe the endpoint endlessly with bad data."""
    for _ in range(5):
        response = rate_limited_client.post("/customers", json={})
        assert response.status_code == 400

    response = rate_limited_client.post("/customers", json=make_customer_payload())

    assert response.status_code == 429


def test_limit_only_applies_to_customer_creation(rate_limited_client):
    """Exhausting the customer-creation limit must not block other routes."""
    for i in range(6):
        rate_limited_client.post("/customers", json=make_customer_payload(i))

    mechanic_response = rate_limited_client.post("/mechanics", json=make_mechanic_payload())
    customers_response = rate_limited_client.get("/customers")

    assert mechanic_response.status_code == 201
    assert customers_response.status_code == 200


def test_rate_limit_headers_are_returned(rate_limited_client):
    """Responses report the limit and how many requests remain, which
    is what makes the limit visible in Postman's Headers tab."""
    response = rate_limited_client.post("/customers", json=make_customer_payload())

    assert response.status_code == 201
    assert response.headers["X-RateLimit-Limit"] == "5"
    assert response.headers["X-RateLimit-Remaining"] == "4"


def test_rate_limiting_is_disabled_in_default_test_config(client):
    """With the normal TestingConfig, more than five customer creations
    all succeed, which is why the rest of the suite is never rate limited."""
    for i in range(6):
        response = client.post("/customers", json=make_customer_payload(i))
        assert response.status_code == 201


def test_create_mechanic_blocked_after_five_requests(rate_limited_client):
    """POST /mechanics carries the same 5-per-hour limit as customer
    creation, for the same reason: creation is the write path most
    open to abuse."""
    for i in range(5):
        response = rate_limited_client.post(
            "/mechanics", json=make_mechanic_payload(email=f"mech{i}@example.com")
        )
        assert response.status_code == 201

    response = rate_limited_client.post(
        "/mechanics", json=make_mechanic_payload(email="mech5@example.com")
    )

    assert response.status_code == 429


def test_delete_customer_blocked_after_ten_requests(rate_limited_client):
    """The 11th DELETE /customers/<id> within an hour returns 429,
    even with no token supplied. The limiter runs before token_required
    (see the decorator order in delete_customer), so every attempt
    counts toward the limit regardless of the 401 each one returns."""
    for _ in range(10):
        response = rate_limited_client.delete("/customers/999")
        assert response.status_code == 401

    response = rate_limited_client.delete("/customers/999")

    assert response.status_code == 429


def test_delete_mechanic_blocked_after_ten_requests(rate_limited_client):
    """Same guarantee as the customer delete limit, for mechanics.
    Mechanic routes carry no token requirement, so these attempts
    reach the actual 404 check rather than being blocked by auth."""
    for _ in range(10):
        response = rate_limited_client.delete("/mechanics/999")
        assert response.status_code == 404

    response = rate_limited_client.delete("/mechanics/999")

    assert response.status_code == 429


def test_default_limit_applies_to_unlimited_routes(rate_limited_client):
    """A route with no route-specific @limiter.limit -- here, GET
    /customers -- still carries the global default (200/day, 50/hour)
    set on the Limiter itself, shown by rate-limit headers being
    present even though nothing decorates the route directly."""
    response = rate_limited_client.get("/customers")

    assert response.status_code == 200
    assert "X-RateLimit-Limit" in response.headers
