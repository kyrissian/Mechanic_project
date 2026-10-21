"""
Structured request logging and correlation IDs.

Render captures whatever this app writes to stdout/stderr and shows it
in the service's own Logs tab -- that's where "monitoring" starts for
a project at this scale, rather than a separate paid logging service
(see README's "Future Extensions" for why that's out of scope here).
Two things make those captured logs actually useful for debugging a
live deploy:

- A short correlation ID tagged onto every log line produced while
  handling one request, so a user's "my request failed" report (which
  can include the X-Request-ID response header below) can be matched
  back to the exact server-side log line, including any traceback the
  unhandled-exception handler in error_handlers.py logs.
- A visible INFO line for every request/response, not just unhandled
  errors -- so a spike in 4xx/5xx responses, or a slow endpoint, shows
  up by scanning Render's logs, without needing to reproduce the
  failure locally first.
"""

import logging
import sys
import time
import uuid

from flask import g, request


class _RequestIdFilter(logging.Filter):
    """Injects the current request's correlation ID into every log
    record passed through this handler.

    Falls back to "-" outside of a request context (e.g. a log line
    emitted during app-factory setup, before any request has come in)
    so the format string below never raises a KeyError.
    """

    def filter(self, record):
        record.request_id = getattr(g, "request_id", "-")
        return True


def configure_logging(app):
    """Attach structured stdout logging and a request correlation ID
    to the given Flask app.

    Called early in create_app(), before routes are registered, so
    every log line emitted anywhere in the app -- including the
    unhandled-exception handler in error_handlers.py -- goes through
    this same formatter and picks up the request ID automatically.
    """
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(
        logging.Formatter("%(asctime)s %(levelname)s [%(request_id)s] %(message)s")
    )
    handler.addFilter(_RequestIdFilter())

    # Replaces Flask's default handler rather than adding alongside it,
    # so every line (ours and Flask/Werkzeug's own) is tagged and
    # formatted consistently instead of only some of them.
    app.logger.handlers = [handler]
    app.logger.setLevel(logging.INFO)
    app.logger.propagate = False

    @app.before_request
    def _assign_request_id():
        # 8 hex characters: long enough to be practically unique across
        # one deploy's log volume, short enough to stay readable inline
        # in a log line or an error response header.
        g.request_id = uuid.uuid4().hex[:8]
        g.request_started_at = time.perf_counter()

    @app.after_request
    def _log_request(response):
        duration_ms = (time.perf_counter() - g.request_started_at) * 1000
        app.logger.info(
            "%s %s -> %s (%.1fms)",
            request.method,
            request.path,
            response.status_code,
            duration_ms,
        )
        # Echoed back to the client so a bug report can be matched to
        # the exact server-side log line above.
        response.headers["X-Request-ID"] = g.request_id
        return response
