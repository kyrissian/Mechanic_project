"""
Production entry point, run by gunicorn on Render.

Separate from run.py (used for local development with the real MySQL
database and Flask's own dev server) for two reasons: gunicorn needs
a plain module-level `app` object to import and serve directly, with
no app.run() call -- gunicorn IS the server, so calling app.run()
here would start a second, redundant server inside the first. And
this file wires up ProductionConfig specifically, so local dev
(run.py, DevelopmentConfig) and the live deployment (this file,
ProductionConfig) can never accidentally point at the wrong database
or the wrong debug setting.

Render's start command for this service should be:
    gunicorn flask_app:app
which imports this module and serves the `app` object below directly
-- gunicorn never executes this file's own code path at all except
for that one import, so there is no "if __name__" guard here the way
run.py has one.
"""

from app import create_app
from config import ProductionConfig

app = create_app(ProductionConfig)
