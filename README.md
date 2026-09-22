# Mechanic Shop Management System

![Python](https://img.shields.io/badge/Python-3776AB?logo=python&logoColor=white&style=flat-square)
![Flask](https://img.shields.io/badge/Flask-000000?logo=flask&logoColor=white&style=flat-square)
![SQLAlchemy](https://img.shields.io/badge/SQLAlchemy-D71F00?logoColor=white&style=flat-square)
![Marshmallow](https://img.shields.io/badge/Marshmallow-black?logoColor=white&style=flat-square)
![MySQL](https://img.shields.io/badge/MySQL-4479A1?logo=mysql&logoColor=white&style=flat-square)
![pytest](https://img.shields.io/badge/pytest-0A9EDC?logo=pytest&logoColor=white&style=flat-square)
![Postman](https://img.shields.io/badge/Postman-FF6C37?logo=postman&logoColor=white&style=flat-square)
![Pylint](https://img.shields.io/badge/Pylint-enabled-brightgreen?style=flat-square)
![GitHub Actions](https://img.shields.io/badge/GitHub_Actions-2088FF?logo=githubactions&logoColor=white&style=flat-square)

A Flask + SQLAlchemy + MySQL backend for a mechanic shop, managing customers, mechanics, and service tickets, with a Marshmallow-validated REST API built on the Application Factory pattern. Built for the "Database Design and Planning with ERDs," "SQLAlchemy Relationships," "Marshmallow Schemas & CRUD Endpoints," and "Application Factory Pattern" course modules.

**Author:** Kathy Booth (with contributions from Claude and GitHub Copilot)

---

## Table of Contents

- [Changelog](#changelog)
- [Tech Stack](#tech-stack)
- [Getting Started](#getting-started)
- [Database Setup](#database-setup)
- [Entity-Relationship Diagram](#entity-relationship-diagram)
- [API Endpoints](#api-endpoints)
- [Rate Limiting & Caching](#rate-limiting--caching)
- [Error Handling](#error-handling)
- [Project Structure](#project-structure)
- [Architecture Notes](#architecture-notes)
- [Testing](#testing)
- [CI](#ci)

---

## Changelog

### 2026-09-21: Rate Limiting and Caching

- Added Flask-Limiter, rate limiting `POST /customers` to 5 requests per hour per client IP -- customer creation is the write path most open to abuse (junk records, or probing which emails are already registered), and rejected requests count toward the limit specifically to stop that kind of probing. Added a dedicated `429` JSON error handler in `app/error_handlers.py` so a client sees which limit it hit, not just Flask-Limiter's default plain-text response.
- Added Flask-Caching, caching `GET /mechanics` for 60 seconds -- the mechanic roster changes rarely but is read often (e.g. whenever someone assigns a mechanic to a ticket). `create_mechanic`, `update_mechanic`, and `delete_mechanic` all explicitly clear the cache after committing, so the 60-second timeout is a backstop rather than the reason data stays fresh -- a client never sees stale data after a write through the API.
- Config split by environment: `DevelopmentConfig` uses `SimpleCache` (in-process) and a `memory://` rate-limit store; `TestingConfig` uses `NullCache` and disables rate limiting entirely, so the existing 51 tests are unaffected. Two test-only config subclasses in `conftest.py`, `RateLimitedTestConfig` and `CachedTestConfig`, opt back into one feature at a time for the tests that need it.
- 10 new tests added: 5 for rate limiting (`test_rate_limiting.py`) and 5 for caching and its invalidation on create/update/delete (`test_mechanic_caching.py`).

### 2026-09-16: Global Error Handling, CI, and Dependency Fix

- Added global error handlers (`app/error_handlers.py`) so unmatched routes, wrong HTTP methods, and malformed/missing JSON bodies all return consistent JSON instead of Flask's default HTML error pages. Not required by the assignment -- added to directly address "thorough error handling for all API calls."
- Added `.github/workflows/ci.yml`: runs the full test suite and Pylint on every push/PR. Also not required by the assignment -- carried over from CI/CD coursework on a prior project. Named `ci.yml` (not `main.yml`) deliberately: unlike that prior project, this API has nowhere to deploy to, so there's no CD half to this workflow.
- Fixed a real gap in `requirements.txt`: `flask-marshmallow`, `marshmallow-sqlalchemy`, and `pylint` had all been installed and used for some time but were never added to the file, which would have broken a fresh install (or CI) with `ModuleNotFoundError`. Verified the fix by installing strictly from `requirements.txt` into a brand-new virtual environment and re-running the full suite.
- Added 4 new tests covering unmatched routes (404), wrong HTTP methods (405), malformed JSON syntax (400), and the wrong `Content-Type` header (415).

### 2026-09-15: Mechanic and ServiceTicket Resources, Application Factory Refactor

- Added full CRUD for `Mechanic` (`/mechanics`): create, get-all, get-one (extra credit), update, delete.
- Added `ServiceTicket` routes (`/service-tickets`): create, get-all, get-one (extra credit), assign-mechanic, remove-mechanic. Deliberately no update or delete for the ticket itself -- completed work should never be erasable.
- Reorganized the project into the Application Factory pattern's blueprint structure: each resource (`customer`, `mechanic`, `service_ticket`) now has its own folder under `app/blueprints/` containing `__init__.py` (creates and registers the Blueprint), `routes.py`, and `schemas.py` -- replacing the earlier flat `app/routes/` and `app/schemas/` folders.
- Moved `config.py` from `app/config.py` to the project root, matching the lesson's file structure.
- Refactored `Customer`'s routes to use a `url_prefix` (`/customers`) with relative paths, matching the pattern used for the two new resources, for consistency across all three.
- 24 new tests added across both new resources' models and routes.

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

| Layer                      | Technology                                                                           |
| -------------------------- | ------------------------------------------------------------------------------------ |
| Web framework              | Flask (Application Factory pattern)                                                  |
| ORM                        | Flask-SQLAlchemy (SQLAlchemy 2.0 `Mapped`/`mapped_column` style)                     |
| Serialization / validation | Flask-Marshmallow, marshmallow-sqlalchemy                                            |
| Database                   | MySQL (via `mysql-connector-python`)                                                 |
| Rate limiting              | Flask-Limiter (in-memory store)                                                      |
| Caching                    | Flask-Caching (`SimpleCache` in development, `NullCache` in tests)                   |
| Config / secrets           | `python-dotenv` (`.env`, gitignored)                                                 |
| Testing                    | pytest, with an isolated in-memory SQLite database                                   |
| Manual API testing         | Postman (collection included in the repo)                                            |
| Linting                    | Pylint                                                                               |
| CI                         | GitHub Actions (test + lint only -- no deploy stage; this API isn't hosted anywhere) |

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

## API Endpoints

All request/response bodies are JSON.

### Customer (`/customers`)

| Method | URL               | Purpose            |
| ------ | ----------------- | ------------------ |
| POST   | `/customers`      | Create a customer  |
| GET    | `/customers`      | List all customers |
| GET    | `/customers/<id>` | Get one customer   |
| PUT    | `/customers/<id>` | Update a customer  |
| DELETE | `/customers/<id>` | Delete a customer  |

### Mechanic (`/mechanics`)

| Method | URL               | Purpose                         |
| ------ | ----------------- | ------------------------------- |
| POST   | `/mechanics`      | Create a mechanic               |
| GET    | `/mechanics`      | List all mechanics              |
| GET    | `/mechanics/<id>` | Get one mechanic (extra credit) |
| PUT    | `/mechanics/<id>` | Update a mechanic               |
| DELETE | `/mechanics/<id>` | Delete a mechanic               |

### Service Ticket (`/service-tickets`)

| Method | URL                                                   | Purpose                               |
| ------ | ----------------------------------------------------- | ------------------------------------- |
| POST   | `/service-tickets`                                    | Create a service ticket               |
| GET    | `/service-tickets`                                    | List all service tickets              |
| GET    | `/service-tickets/<id>`                               | Get one service ticket (extra credit) |
| PUT    | `/service-tickets/<id>/assign-mechanic/<mechanic_id>` | Assign a mechanic to a ticket         |
| PUT    | `/service-tickets/<id>/remove-mechanic/<mechanic_id>` | Remove a mechanic from a ticket       |

Deliberately no `PUT`/`DELETE` for the ticket resource itself -- a completed or in-progress service record should never be silently overwritten or erased.

---

## Rate Limiting & Caching

| Route             | Behavior                             | Why                                                                                                                                                                                                                                                     |
| ----------------- | ------------------------------------ | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `POST /customers` | Rate limited: 5 requests / hour / IP | Creation is the write path most open to abuse -- an unlimited endpoint could be flooded with junk records or used to probe which emails are already registered. Rejected (400) attempts still count toward the limit, which is what stops that probing. |
| `GET /mechanics`  | Cached: 60 seconds                   | The mechanic roster is read often (e.g. every time a mechanic is assigned to a ticket) but changes rarely, so most requests can be served from memory instead of hitting the database.                                                                  |

No other routes are limited or cached: `/customers` reads return personal data that changes on every write, so they're always fresh; `/service-tickets` changes too often for a timed cache to help.

A limited or cached response carries the same status codes and JSON shape described in [Error Handling](#error-handling) and [API Endpoints](#api-endpoints) above, with two additions:

- Exceeding the limit on `POST /customers` returns `429` with `{"error": "Rate limit exceeded", "detail": "5 per 1 hour"}`.
- Every response includes `X-RateLimit-Limit`, `X-RateLimit-Remaining`, and `X-RateLimit-Reset` headers, so the current state of the limit is visible in Postman without waiting to be blocked.

Cache invalidation is explicit, not timeout-only: `create_mechanic`, `update_mechanic`, and `delete_mechanic` all call `cache.delete()` on the cached key immediately after committing, so a client making a write through the API always sees its own change on the very next `GET /mechanics` -- the 60-second timeout only matters for a change made outside the API (e.g. directly in MySQL Workbench).

---

## Error Handling

Two global error handlers (`app/error_handlers.py`) guarantee every response from this API is JSON, including failures that never reach an actual route function:

- Any HTTP-level error (unmatched route → 404, wrong HTTP method → 405, malformed JSON body → 400, wrong `Content-Type` header → 415, etc.) returns `{"error": "..."}` with the matching status code, instead of Flask's default HTML error page.
- Any unexpected exception in application code is caught and logged server-side, and returns a generic `{"error": "An unexpected server error occurred."}` with a 500, rather than leaking a raw traceback to the client.
- Exceeding a rate limit returns `429` with `{"error": "Rate limit exceeded", "detail": "..."}`, where `detail` names the specific limit that was hit (e.g. `"5 per 1 hour"`). Flask checks status-code handlers before class handlers, so this one takes priority over the generic HTTP-level handler above.

This is separate from, and doesn't interfere with, the specific `{"error": "Customer not found."}`-style responses already written into each route for expected cases like a missing id or a duplicate email -- those are returned directly by the view functions and never touch these handlers at all.

---

## Project Structure

```
Mechanic_project/
  .env                        # local secrets, gitignored
  .gitignore
  .pylintrc
  requirements.txt
  config.py                   # DevelopmentConfig (MySQL) / TestingConfig (SQLite)
  run.py                      # entry point: builds real MySQL tables, starts dev server
  Mechanic_Shop_API.postman_collection.json   # exported Postman requests for every endpoint
  .github/
    workflows/
      ci.yml                   # runs pytest + pylint on push/PR
  app/
    __init__.py                # app factory (create_app())
    extensions.py               # shared db / ma / limiter / cache instances
    error_handlers.py           # global JSON error handlers
    models/
      __init__.py
      customer.py
      mechanic.py
      service_ticket.py
      service_mechanics.py       # service_mechanics junction table
    blueprints/
      __init__.py
      customer/
        __init__.py               # creates and registers the Customer blueprint
        routes.py                 # CRUD routes for /customers
        schemas.py                # CustomerSchema
      mechanic/
        __init__.py
        routes.py                 # CRUD routes for /mechanics
        schemas.py                # MechanicSchema
      service_ticket/
        __init__.py
        routes.py                 # routes for /service-tickets
        schemas.py                # ServiceTicketSchema (include_fk=True)
  tests/
    __init__.py
    conftest.py                 # shared pytest fixtures
    test_customer_model.py
    test_mechanic_model.py
    test_service_ticket_model.py
    test_customer_routes.py
    test_mechanic_routes.py
    test_service_ticket_routes.py
    test_rate_limiting.py
    test_mechanic_caching.py
    test_error_handlers.py
```

---

## Architecture Notes

### Why not a single `app.py`, like the lesson shows?

The lesson's simplest example puts everything — Flask app creation, the database connection string, `db = SQLAlchemy()`, and the models — into one file. This project splits those same responsibilities across several files instead, for two concrete reasons:

1. **Testability.** A single module-level `app = Flask(__name__)` gets created once, permanently wired to the real MySQL database, the moment the file is imported — there's no clean way for a test to get its own separate, disposable app pointed at a fake database instead. Wrapping app creation in a `create_app()` function (the "app factory" pattern) means each test can call `create_app(TestingConfig)` to get a fresh, fully isolated app backed by a fast in-memory database, without ever touching real data.

2. **Maintainability.** Config, the shared `db`/`ma` instances, each model, and each resource's routes/schema all have one clear, single-purpose file or folder.

`run.py` is functionally where the lesson's `app.py` ends up: it calls `create_app()`, runs `db.create_all()` to build the real tables, and starts the dev server.

### Blueprints, one folder per resource

Following the Application Factory Pattern lesson's own file structure, each resource's routes and schema live together in their own folder under `app/blueprints/`, rather than in project-wide `routes/`/`schemas/` folders (an earlier structure this project briefly used). Each blueprint's `__init__.py` creates the `Blueprint` object, then imports its own `routes.py` at the very bottom — after the `Blueprint` already exists — so every `@blueprint.route(...)` decorator in `routes.py` attaches correctly. `routes.py` in turn imports the blueprint back from `__init__.py`. This two-file, bottom-of-file-import pattern is the standard way to structure Flask blueprints without a circular import.

Each blueprint is registered in `app/__init__.py` with a `url_prefix` matching the resource's plural name (`/customers`, `/mechanics`, `/service-tickets`), so the routes inside each `routes.py` only need their path relative to that prefix.

### Provider-style separation

- `app/extensions.py` holds the shared `db`, `ma`, `limiter`, and `cache` objects. It's kept separate from `app/__init__.py` specifically to avoid a circular import: model/schema files need to import `db`/`ma` to define their columns/fields, and the app factory needs to import the models to register their tables.
- Model files import `service_mechanics.py`'s `service_mechanics` table by string name (`secondary="service_mechanics"`) rather than importing the `Table` object directly, avoiding another circular-import path between `mechanic.py` and `service_ticket.py`.
- `ServiceTicketSchema` sets `include_fk = True` in its `Meta` class specifically because `SQLAlchemyAutoSchema` excludes foreign key columns by default -- without it, `customer_id` (the field a client needs to send when creating a ticket) would be silently missing from the schema entirely.
- `cache = Cache()` in `extensions.py` is deliberately created with no config, unlike the lesson's example. Config passed directly to the `Cache()` constructor overrides `app.config`, which would make it impossible for `TestingConfig` to switch caching off -- so the backend (`SimpleCache`, `NullCache`) is set entirely through `config.py` instead.

---

## Testing

### Automated tests

Each model has its own test file, written alongside the model as it was built, plus a matching route test file for its HTTP endpoints:

- **`test_customer_model.py`** / **`test_customer_routes.py`** — model-level creation and unique-email enforcement; every `/customers` endpoint including duplicate-email and missing-field rejection, and 404s for bad ids.
- **`test_mechanic_model.py`** / **`test_mechanic_routes.py`** — model-level creation and the many-to-many relationship to tickets; every `/mechanics` endpoint including the extra-credit get-one route.
- **`test_service_ticket_model.py`** / **`test_service_ticket_routes.py`** — model-level creation and the many-to-many relationship to mechanics; every `/service-tickets` endpoint including assign/remove-mechanic edge cases (duplicate assignment, removing an unassigned mechanic, ticket/mechanic not found).
- **`test_rate_limiting.py`** — confirms `POST /customers` allows 5 requests per hour then returns 429; that rejected requests still count toward the limit; that the limit doesn't block other routes; that rate-limit headers are present; and that the default test config leaves rate limiting off.
- **`test_mechanic_caching.py`** — confirms `GET /mechanics` is served from cache (a direct database insert the API never saw stays invisible until the cache clears); that caching is off by default in tests; and that create, update, and delete on `/mechanics` each immediately refresh the cached list.
- **`test_error_handlers.py`** — confirms unmatched routes, wrong HTTP methods, malformed JSON, and wrong `Content-Type` all return consistent JSON rather than Flask's default HTML error pages.

Tests run against a temporary in-memory SQLite database (via `TestingConfig`), never the real MySQL database — so the suite is fast and never at risk of touching or corrupting real data.

Run the full suite:

```powershell
python -m pytest -v
```

Currently: **61 tests, all passing.**

### Testing with Postman

In addition to the automated test suite, every endpoint was also manually verified against the real running app and the real MySQL database, using Postman. The saved requests are exported as `Mechanic_Shop_API.postman_collection.json` in the project root.

To use it:

1. Open Postman.
2. Click **Import** and select `Mechanic_Shop_API.postman_collection.json`.
3. Make sure the app is running locally (`python run.py`).
4. Open the `Mechanic Shop API` collection and send any request — each one is pre-filled with the correct method, URL, and (where needed) a sample JSON body.

See [API Endpoints](#api-endpoints) above for the full list covered.

---

## CI

`.github/workflows/ci.yml` runs on every push and pull request to `main`: installs dependencies from `requirements.txt`, runs the full pytest suite, then runs Pylint. Because tests use an in-memory SQLite database rather than a real MySQL connection, this workflow needs no database service or secrets configured at all.

This wasn't required by the assignment -- it's carried over from CI/CD coursework on a prior project. Unlike that project, this API isn't deployed anywhere, so there's no CD (deployment) stage here, which is also why this file is named `ci.yml` rather than `main.yml`.

---

## Submission Checklist

- [x] Blueprints registered for `customer`, `mechanic`, and `service_ticket`, each with its own `url_prefix`
- [x] Full CRUD implemented for `Customer` and `Mechanic`; `ServiceTicket` create/list/assign-mechanic/remove-mechanic (no update/delete, by design)
- [x] Marshmallow schemas validate and serialize every resource
- [x] `POST /customers` rate limited (5/hour/IP); `GET /mechanics` cached (60s) with explicit invalidation on write
- [x] Postman collection included in the repo and covers every endpoint
- [x] 61 automated tests passing (`python -m pytest -v`)
- [x] Pylint clean (`python -m pylint app tests config.py`)
- [x] CI workflow passing on GitHub Actions
