# Mechanic Shop Management System

![Python](https://img.shields.io/badge/Python-3776AB?logo=python&logoColor=white&style=flat-square)
![Flask](https://img.shields.io/badge/Flask-000000?logo=flask&logoColor=white&style=flat-square)
![SQLAlchemy](https://img.shields.io/badge/SQLAlchemy-D71F00?logoColor=white&style=flat-square)
![MySQL](https://img.shields.io/badge/MySQL-4479A1?logo=mysql&logoColor=white&style=flat-square)
![pytest](https://img.shields.io/badge/pytest-0A9EDC?logo=pytest&logoColor=white&style=flat-square)
![Pylint](https://img.shields.io/badge/Pylint-enabled-brightgreen?style=flat-square)

A Flask + SQLAlchemy + MySQL backend for a mechanic shop, managing customers, mechanics, and service tickets. Built for the "Database Design and Planning with ERDs" and "SQLAlchemy Relationships" course modules.

---

## Table of Contents

- [Changelog](#changelog)
- [Tech Stack](#tech-stack)
- [Getting Started](#getting-started)
- [Database Setup](#database-setup)
- [Entity-Relationship Diagram](#entity-relationship-diagram)
- [Project Structure](#project-structure)
- [Architecture Notes](#architecture-notes)
- [Testing](#testing)

---

## Changelog

### 2026-09-14: ERD Correction

- The follow-up "SQLAlchemy Relationships" lesson provided the class's official ERD, which differed from the earlier draft ERD these models were first built against. Rebuilt all three models and the junction table to match it exactly: `Customer` now uses a single `name` field (was `first_name`/`last_name`, no `address`); `Mechanic` gained `email`, lost `address`, and `salary` changed from `INT` to `FLOAT`; `ServiceTicket` was significantly simplified to just `vin`, `service_date`, and `service_desc` (was `date_received`/`make`/`model`/`year`/`work_description`/`status`); the junction table was renamed `service_mechanics` with columns `ticket_id`/`mechanic_id` (was `st_mechanic` with `st_id`/`mech_id`). Tests were updated to match, following the same TDD habit as the original build.

### 2026-09-14: Initial Models & Project Setup

- Set up the project as a Flask application using the app factory pattern (`create_app()`), rather than the single-file `app.py` style shown in the lesson.
- Configured two separate environments: a real MySQL connection for development (credentials via `.env`, never committed), and an isolated in-memory SQLite database for tests.
- Built `Customer`, `Mechanic`, and `ServiceTicket` models matching the class-provided ERD, plus the `st_mechanic` junction table for the many-to-many relationship between mechanics and service tickets.
- Wrote model-level tests alongside each model as it was built (TDD), rather than after the fact.
- Created `run.py` as the actual entry point that builds the real MySQL tables and starts the dev server.

---

## Tech Stack

| Layer            | Technology                                                       |
| ---------------- | ---------------------------------------------------------------- |
| Web framework    | Flask                                                            |
| ORM              | Flask-SQLAlchemy (SQLAlchemy 2.0 `Mapped`/`mapped_column` style) |
| Database         | MySQL (via `mysql-connector-python`)                             |
| Config / secrets | `python-dotenv` (`.env`, gitignored)                             |
| Testing          | pytest, with an isolated in-memory SQLite database               |
| Linting          | Pylint                                                           |

---

## Getting Started

### Prerequisites

- Python 3.x
- MySQL Workbench (or another way to run a local MySQL server)

### Installation

```powershell
git clone <repo-url>
cd Mechanic_project
python -m venv venv
venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

### Environment Variables

Create a `.env` file in the project root:

```
DB_USER=root
DB_PASSWORD=your_actual_mysql_password
DB_HOST=localhost
DB_NAME=mechanic_shop
```

### Run locally

```powershell
python run.py
```

This creates every table defined by the models (if they don't already exist) in the real MySQL database configured above, then starts the Flask dev server.

---

## Database Setup

1. Open MySQL Workbench and connect to your local MySQL instance.
2. Run `CREATE DATABASE mechanic_shop;` (or whatever name you used for `DB_NAME` above).
3. Run `python run.py` once — this creates all the tables automatically from the models. No manual `CREATE TABLE` statements needed.

---

## Entity-Relationship Diagram

Models match the class-provided ERD exactly:

- **Customer** — `id`, `name`, `email`, `phone`
- **Service_Ticket** — `id`, `vin`, `service_date`, `service_desc`, plus a foreign key to `Customer`
- **Mechanic** — `id`, `name`, `email`, `phone`, `salary` (float)
- **Service_Mechanics** (junction table) — `ticket_id` + `mechanic_id`, linking `Service_Ticket` and `Mechanic`

Relationships:

- **Customer → Service_Ticket**: one-to-many (a customer can have many service tickets, each ticket belongs to exactly one customer)
- **Service_Ticket ↔ Mechanic**: many-to-many, via `Service_Mechanics` (a ticket can require multiple mechanics, a mechanic can work on multiple tickets)

Note: `service_date` is stored as a string (`VARCHAR`), not a `DATE` column, and the junction table's two columns aren't marked as a composite primary key -- both match the ERD and the lesson's own example exactly, rather than "improving" on the given design, since these models are graded against this specific diagram.

---

## Project Structure

```
Mechanic_project/
  .env                        # local secrets, gitignored
  .gitignore
  .pylintrc
  requirements.txt
  run.py                      # entry point: builds real MySQL tables, starts dev server
  app/
    __init__.py                # app factory (create_app())
    config.py                  # DevelopmentConfig (MySQL) / TestingConfig (SQLite)
    extensions.py               # shared db = SQLAlchemy() instance
    models/
      __init__.py
      customer.py
      mechanic.py
      service_ticket.py
      service_mechanics.py       # service_mechanics junction table
  tests/
    __init__.py
    conftest.py                 # shared pytest fixtures
    test_customer_model.py
    test_mechanic_model.py
    test_service_ticket_model.py
```

---

## Architecture Notes

### Why not a single `app.py`, like the lesson shows?

The lesson's example puts everything — Flask app creation, the database connection string, `db = SQLAlchemy()`, and the models — into one file. This project splits those same responsibilities across several files instead, for two concrete reasons:

1. **Testability.** A single module-level `app = Flask(__name__)` gets created once, permanently wired to the real MySQL database, the moment the file is imported — there's no clean way for a test to get its own separate, disposable app pointed at a fake database instead. Wrapping app creation in a `create_app()` function (the "app factory" pattern) means each test can call `create_app(TestingConfig)` to get a fresh, fully isolated app backed by a fast in-memory database, without ever touching real data. This is what makes writing a test alongside every model practical, rather than tests needing to either hit the real database or be bolted on awkwardly after the fact.

2. **Maintainability.** Config, the shared `db` instance, and each model each have one clear, single-purpose file. As routes get added in a later module, they'll have an obvious home (e.g. a `routes/` folder) instead of getting stacked into an already-crowded single file.

`run.py` is functionally where the lesson's `app.py` ends up: it calls `create_app()`, runs `db.create_all()` to build the real tables, and starts the dev server — same end result, just assembled from the reusable pieces above instead of written inline.

### Provider-style separation

- `app/extensions.py` holds the single shared `db` object. It's kept separate from `app/__init__.py` specifically to avoid a circular import: model files need to import `db` to define their columns, and the app factory needs to import the models to register their tables — if `db` lived in `app/__init__.py`, those two imports would depend on each other.
- Model files import `associations.py`'s `st_mechanic` table by string name (`secondary="st_mechanic"`) rather than importing the `Table` object directly, avoiding another circular-import path between `mechanic.py` and `service_ticket.py`.

---

## Testing

Each model has its own test file, written alongside the model as it was built rather than afterward:

- **`test_customer_model.py`** — creating a customer with all fields, and enforcing that email must be unique.
- **`test_mechanic_model.py`** — creating a mechanic, and confirming a single mechanic can be linked to multiple service tickets (the many-to-many relationship).
- **`test_service_ticket_model.py`** — creating a ticket linked to its customer, and confirming a single ticket can require multiple mechanics (the other direction of that same many-to-many relationship).

Tests run against a temporary in-memory SQLite database (via `TestingConfig`), never the real MySQL database — so the suite is fast and never at risk of touching or corrupting real data.

Run the full suite:

```powershell
python -m pytest -v
```

Currently: **6 tests, all passing.**
