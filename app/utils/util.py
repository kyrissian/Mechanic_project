"""
Token authentication utilities.

Two separate token types exist, both signed with the same
SECRET_KEY but distinguished by a "type" claim in the payload:
customer tokens (encode_token / token_required) and mechanic tokens
(encode_mechanic_token / mechanic_token_required). Without this
distinction, a valid customer token and a valid mechanic token would
be indistinguishable at decode time -- both are just JWTs signed with
the same key -- so a customer could potentially authenticate against
a mechanic-only route (or vice versa) using their own token, if their
id happened to collide with a real mechanic id. The "type" claim
closes that gap: each decorator explicitly checks it in addition to
the signature itself.

manager_required builds on mechanic_token_required, additionally
checking that the decoded token's role is "manager" -- so a plain
mechanic token is correctly rejected from manager-only routes even
though it's a fully valid, unexpired mechanic token.
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
        "type": "customer",
    }
    return jwt.encode(payload, current_app.config["SECRET_KEY"], algorithm="HS256")


def encode_mechanic_token(mechanic_id, role):
    """Create a JWT identifying the given mechanic and their role,
    valid for 1 hour. role is carried in the token itself (rather
    than looked up fresh from the database on every request) so
    manager_required can check it without an extra query -- it's
    still only ever set here, at login, from the mechanic's real
    database row.
    """
    payload = {
        "exp": datetime.now(timezone.utc) + timedelta(hours=1),
        "iat": datetime.now(timezone.utc),
        "sub": str(mechanic_id),
        "type": "mechanic",
        "role": role,
    }
    return jwt.encode(payload, current_app.config["SECRET_KEY"], algorithm="HS256")


def _decode_bearer_token(expected_type):
    """Shared logic for pulling a Bearer token out of the
    Authorization header and decoding it. Returns (data, None) on
    success, or (None, (response, status)) on any failure, so callers
    can `return error` directly without duplicating the same failure
    branches in both token_required and mechanic_token_required.
    """
    auth_header = request.headers.get("Authorization")
    if not auth_header or not auth_header.startswith("Bearer "):
        return None, (jsonify({"error": "Token is missing."}), 401)
    token = auth_header.split(" ", 1)[1]

    try:
        data = jwt.decode(
            token, current_app.config["SECRET_KEY"], algorithms=["HS256"]
        )
    except ExpiredSignatureError:
        return None, (jsonify({"error": "Token has expired."}), 401)
    except JWTError:
        return None, (jsonify({"error": "Invalid token."}), 401)

    # A structurally valid, correctly signed token of the WRONG type
    # (e.g. a customer token presented to a mechanic-only route) is
    # treated identically to a garbled one -- same message, same
    # status -- so a caller can't distinguish "wrong token type" from
    # "invalid token" and use that to probe which type a route expects.
    if data.get("type") != expected_type:
        return None, (jsonify({"error": "Invalid token."}), 401)

    return data, None


def token_required(f):
    """Require a valid customer Bearer token in the Authorization
    header. On success, passes the token's customer_id as the first
    positional argument to the wrapped route function.
    """

    @wraps(f)
    def decorated(*args, **kwargs):
        data, error = _decode_bearer_token(expected_type="customer")
        if error:
            return error
        customer_id = int(data["sub"])
        return f(customer_id, *args, **kwargs)

    return decorated


def mechanic_token_required(f):
    """Require a valid mechanic Bearer token in the Authorization
    header. On success, passes the token's mechanic_id and role as
    the first two positional arguments to the wrapped route function.
    """

    @wraps(f)
    def decorated(*args, **kwargs):
        data, error = _decode_bearer_token(expected_type="mechanic")
        if error:
            return error
        mechanic_id = int(data["sub"])
        role = data.get("role")
        return f(mechanic_id, role, *args, **kwargs)

    return decorated


def manager_required(f):
    """Require a valid mechanic Bearer token AND that its role is
    "manager". On success, passes the token's mechanic_id only --
    role is not forwarded, since by this point it's already been
    confirmed to be "manager".

    Built on top of mechanic_token_required rather than duplicating
    its token-decoding logic: this function only adds the role check,
    then delegates everything else to the decorator it wraps.

    The inner wrapper's own parameter is deliberately named
    requester_id rather than mechanic_id: several routes this
    decorates (update_mechanic, delete_mechanic, assign_mechanic,
    remove_mechanic) have a URL parameter ALSO named mechanic_id.
    Flask passes URL parameters as keyword arguments, so if this
    wrapper's own parameter were also named mechanic_id, Python would
    raise "got multiple values for argument 'mechanic_id'" the moment
    both the positional value from the token and the keyword value
    from the URL tried to bind to the same parameter name.
    """

    @wraps(f)
    def check_role(requester_id, role, *args, **kwargs):
        if role != "manager":
            return jsonify({"error": "This action requires manager access."}), 403
        return f(requester_id, *args, **kwargs)

    return mechanic_token_required(check_role)
