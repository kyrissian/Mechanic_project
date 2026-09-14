"""
Entry point for running the app against the real database.

Running this file directly creates every table our models define
(Customer, Mechanic, ServiceTicket, st_mechanic) in the actual MySQL
database configured in .env -- unlike our tests, which only ever
touch the temporary, in-memory database and never create anything
real.
"""

from app import create_app
from app.extensions import db

app = create_app()

if __name__ == "__main__":
    with app.app_context():
        db.create_all()
        print("Tables created successfully.")

    app.run(debug=True)
