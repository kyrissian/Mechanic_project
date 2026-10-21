"""
Health check route, for uptime monitoring and deploy verification.

This is what the "Deployment" feedback's "monitoring tools... alerts
for failed deployments" points at in practice for a project at this
scale: a plain, unauthenticated GET endpoint that an external uptime
monitor (e.g. UptimeRobot, Better Uptime, or Render's own health
check setting) can poll every few minutes, alerting someone the
moment it stops returning 200 -- which catches the live site going
down between deploys, not just a deploy failing in CI (the `deploy`
job in ci_cd.yml already surfaces that separately, as a failed GitHub
Actions run).

Checks real database connectivity rather than only "the process is
running", since a web dyno that's up but can't reach its database is
not actually healthy -- Flask would still accept the TCP connection
and return something, just a 500 on every real route.
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
    """Report service health for uptime monitoring.

    Returns 200 with {"status": "ok"} when the database is reachable,
    or 503 with {"status": "error", "detail": ...} otherwise -- a
    distinct status code a monitor can alert on, separate from a
    generic 500 that could also mean an unrelated application bug.
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
