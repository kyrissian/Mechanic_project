"""
Token authentication utilities.

encode_token() issues a JWT identifying a single customer.
token_required() is a decorator that guards a route: it requires a
valid Bearer token in the Authorization header, then passes the
token's customer_id through to the wrapped route function as its
first argument.
"""

from datetime import datetime, timedelta, timezone
from functools import wraps

from flask import current_app, jsonify, request
from jose import jwt
from jose.exceptions import ExpiredSignatureError, JWTError


def encode_token(customer_id):
    """Create a JWT identifying the given customer, valid for 1 hour.

    Signed with the running app's SECRET_KEY (config.py, itself
    sourced from the .env SECRET_KEY variable) rather than a
    hardcoded constant. This guarantees a token can never be encoded
    with a different key than token_required() decodes with, and
    keeps the real key out of source control.
    """
    payload = {
        "exp": datetime.now(timezone.utc) + timedelta(hours=1),
        "iat": datetime.now(timezone.utc),
        "sub": str(customer_id),
    }
    return jwt.encode(payload, current_app.config["SECRET_KEY"], algorithm="HS256")


def token_required(f):
    """Require a valid Bearer token in the Authorization header.

    On success, passes the token's customer_id as the first positional
    argument to the wrapped route function. Returns 401 for a missing,
    malformed, expired, or otherwise invalid token, before the wrapped
    function ever runs.
    """

    @wraps(f)
    def decorated(*args, **kwargs):
        auth_header = request.headers.get("Authorization")
        if not auth_header or not auth_header.startswith("Bearer "):
            return jsonify({"error": "Token is missing."}), 401
        token = auth_header.split(" ", 1)[1]

        try:
            data = jwt.decode(
                token, current_app.config["SECRET_KEY"], algorithms=["HS256"]
            )
        except ExpiredSignatureError:
            return jsonify({"error": "Token has expired."}), 401
        except JWTError:
            return jsonify({"error": "Invalid token."}), 401

        customer_id = int(data["sub"])
        return f(customer_id, *args, **kwargs)

    return decorated
