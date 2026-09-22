"""
Global error handlers.

Without these, an unmatched route, a wrong HTTP method, or a
malformed/missing JSON body all fall through to Flask's default
error pages -- plain HTML, not JSON -- which is inconsistent for a
REST API that returns JSON everywhere else. These three handlers cover
every case:

- HTTPException covers all the "expected" HTTP errors (404 unmatched
  route, 405 wrong method, 400 malformed JSON body, 415 wrong
  Content-Type, etc.) with one handler instead of registering one per
  status code.
- The 429 handler covers rate-limit violations raised by Flask-Limiter.
  Flask checks status-code handlers before class handlers, so this one
  takes priority over the generic HTTPException handler and lets us
  return a clearer message that includes the limit that was exceeded.
- The bare Exception handler is a last-resort safety net for any bug
  in our own code that would otherwise leak a raw traceback (or, in
  production, a bare "Internal Server Error" HTML page) to the client.

Registering a handler here does not affect the explicit
`return jsonify({"error": "..."}), 404`-style responses already
written in each blueprint's routes -- those are values returned
directly by a view function, not raised exceptions, so Flask never
routes them through these handlers at all.
"""

from flask import jsonify
from werkzeug.exceptions import HTTPException


def register_error_handlers(app):
    """Attach the shared error handlers to the given Flask app."""

    @app.errorhandler(HTTPException)
    def handle_http_exception(e):
        """Turns any HTTP-level error (400, 404, 405, 415, ...) into
        consistent JSON instead of Flask's default HTML error page."""
        return jsonify({"error": e.description}), e.code

    @app.errorhandler(Exception)
    def handle_unexpected_error(e):
        """Catches anything our own code doesn't handle, so a bug
        never surfaces a raw traceback or an HTML 500 page."""
        app.logger.exception("Unhandled exception: %s", e)
        return jsonify({"error": "An unexpected server error occurred."}), 500

    @app.errorhandler(429)
    def handle_rate_limit_exceeded(e):
        """Return a JSON 429 when a client exceeds a rate limit.

        `e.description` holds the limit that was hit (e.g. "5 per 1 hour"),
        which tells the client what the rule is.
        """
        return jsonify({"error": "Rate limit exceeded", "detail": str(e.description)}), 429
