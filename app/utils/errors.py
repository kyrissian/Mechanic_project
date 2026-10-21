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


def not_found_response(resource, detail=None):
    """Build a standard 404 for "X not found", shared by every
    blueprint -- previously each route built this same
    jsonify({"error": "..."}), 404 shape inline, with the resource
    name as the only thing that varied.

    `detail`, when given, is folded into the message as extra
    identifying context (not_found_response("Mechanic", "id 7") ->
    "Mechanic id 7 not found."), for the handful of call sites that
    need to name which id was missing rather than just the resource
    type.
    """
    message = f"{resource} not found." if detail is None else f"{resource} {detail} not found."
    return jsonify({"error": message}), 404
