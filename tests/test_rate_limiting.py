"""Tests for rate limiting on POST /customers (5 per hour per client)."""


def make_customer_payload(index=0, **overrides):
    """Default JSON body for creating a customer. `index` makes each
    email unique so repeated creates don't trip the duplicate-email check."""
    payload = {
        "name": f"Customer {index}",
        "email": f"customer{index}@example.com",
        "phone": "555-123-4567",
    }
    payload.update(overrides)
    return payload


def make_mechanic_payload():
    """Default JSON body for creating a mechanic."""
    return {
        "name": "Alex Chen",
        "email": "alex@example.com",
        "phone": "555-987-6543",
        "salary": 55000.00,
    }


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
