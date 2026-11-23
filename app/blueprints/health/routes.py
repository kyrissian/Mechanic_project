"""
Health check routes, for uptime monitoring and deploy verification.

Two plain, unauthenticated GET endpoints:

* GET /health -- a lightweight liveness check. It reports that the web
  process is up and answering requests, and deliberately does NOT touch
  the database. An external uptime monitor (e.g. UptimeRobot) polls this
  every few minutes; if it queried the database each time, a serverless
  database with scale-to-zero (such as Neon's free tier) would never get
  a quiet stretch long enough to sleep, and would burn through its
  monthly compute allowance.
* GET /health/db -- a deeper readiness check that confirms real database
  connectivity. It is meant to be called by hand, or from a deploy
  verification step, and should not be pointed at a frequent monitor.

A web process that is up but cannot reach its database is not fully
healthy, which is why the deeper check exists -- it just is not the one
that should run around the clock.
"""

from flask import jsonify
from sqlalchemy import text

from app.blueprints.health import health_bp
from app.extensions import db, limiter

# Exempted from rate limiting: an uptime monitor polling every few
# minutes (a reasonable interval for catching an outage quickly) would
# otherwise run into the 200-per-day default limit applied to every
# other route, and getting rate-limited is exactly the wrong failure
# mode for a route whose entire job is reporting whether the service
# is reachable.
limiter.exempt(health_bp)


@health_bp.route("/health", methods=["GET"])
def health_check():
    """Report that the service is up, without touching the database.

    Returns 200 with {"status": "ok"} whenever the web process can
    answer a request. Safe for a monitor to poll as often as it likes,
    because it never wakes a sleeping database.
    """
    return jsonify({"status": "ok"}), 200


@health_bp.route("/health/db", methods=["GET"])
def health_check_db():
    """Report whether the database is reachable.

    Returns 200 with {"status": "ok"} when the database answers, or 503
    with {"status": "error", "detail": ...} otherwise -- a distinct
    status code that can be told apart from a generic 500 caused by an
    unrelated application bug. This runs a real query, so it will wake a
    sleeping database; call it by hand rather than from a frequent
    monitor.
    """
    try:
        db.session.execute(text("SELECT 1"))
    except Exception as e:  # pylint: disable=broad-exception-caught
        # Deliberately broad: any failure reaching the database (wrong
        # credentials, database asleep/unreachable, network issue)
        # should report unhealthy, not bubble up as an unhandled 500
        # from this route specifically.
        return jsonify({"status": "error", "detail": str(e)}), 503

    return jsonify({"status": "ok"}), 200
