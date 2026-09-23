"""
Shared error-response helpers.

Keeps every route's validation-failure response in the same shape as
every other error in this API ({"error": "...", ...}), rather than
Marshmallow's raw e.messages dict, which has no "error" key at all
and would be the one inconsistent response shape in the whole API.
"""

from flask import jsonify


def validation_error_response(e):
    """Build a standard 400 response from a Marshmallow ValidationError.

    `details` carries Marshmallow's own field-by-field messages
    unchanged, so no validation information is lost -- only wrapped
    in the same {"error": ...} envelope every other failure uses.
    """
    return jsonify({"error": "Validation failed.", "details": e.messages}), 400
