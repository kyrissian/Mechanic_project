# Mechanic Shop Management System

![Python](https://img.shields.io/badge/Python-3776AB?logo=python&logoColor=white&style=flat-square)
![Flask](https://img.shields.io/badge/Flask-000000?logo=flask&logoColor=white&style=flat-square)
![SQLAlchemy](https://img.shields.io/badge/SQLAlchemy-D71F00?logoColor=white&style=flat-square)
![Marshmallow](https://img.shields.io/badge/Marshmallow-black?logoColor=white&style=flat-square)
![MySQL](https://img.shields.io/badge/MySQL-4479A1?logo=mysql&logoColor=white&style=flat-square)
![JWT](https://img.shields.io/badge/JWT-black?logo=jsonwebtokens&logoColor=white&style=flat-square)
![pytest](https://img.shields.io/badge/pytest-0A9EDC?logo=pytest&logoColor=white&style=flat-square)
![Postman](https://img.shields.io/badge/Postman-FF6C37?logo=postman&logoColor=white&style=flat-square)
![Pylint](https://img.shields.io/badge/Pylint-enabled-brightgreen?style=flat-square)
![GitHub Actions](https://img.shields.io/badge/GitHub_Actions-2088FF?logo=githubactions&logoColor=white&style=flat-square)

A Flask + SQLAlchemy + MySQL backend for a mechanic shop, managing customers, mechanics, and service tickets, with a Marshmallow-validated, JWT-authenticated REST API built on the Application Factory pattern. Built for the "Database Design and Planning with ERDs," "SQLAlchemy Relationships," "Marshmallow Schemas & CRUD Endpoints," "Application Factory Pattern," "Rate Limiting and Caching," and "Token Authentication" course modules.

**Author:** Kathy Booth (with contributions from Claude and GitHub Copilot)

---

## Table of Contents

- [Changelog](#changelog)
- [Tech Stack](#tech-stack)
- [Getting Started](#getting-started)
- [Database Setup](#database-setup)
- [Entity-Relationship Diagram](#entity-relationship-diagram)
- [API Endpoints](#api-endpoints)
- [Authentication](#authentication)
- [Rate Limiting & Caching](#rate-limiting--caching)
- [Error Handling](#error-handling)
- [Project Structure](#project-structure)
- [Architecture Notes](#architecture-notes)
- [Testing](#testing)
- [CI](#ci)

---

## Changelog

### 2026-09-23: Token Authentication and Standardized Error Handling

- Added JWT-based token authentication for the `Customer` resource, per the Token Authentication lesson. `POST /customers/login` exchanges an email and password for a token; `GET /customers/my-tickets`, `PUT /customers/<id>`, and `DELETE /customers/<id>` all require a valid token, and the latter two additionally verify the token's customer matches the id in the URL, so a customer can only ever modify or delete their own account. See [Authentication](#authentication) for the full reasoning behind which routes were and weren't protected.
- `Customer` gained a `password_hash` column, hashed with `werkzeug.security` and never returned in any response. This is **not** part of the class-provided ERD -- documented here as a deliberate, necessary extension for this lesson, same category as the extra-credit GET-one routes, rather than a silent departure from the diagram.
- Standardized every validation-failure response across all three resources to the same `{"error": "...", "details": {...}}` envelope every other error in this API already used -- closing a real gap flagged in instructor feedback on the previous submission ("comprehensive error handling and custom error messages"). Previously, a Marshmallow validation failure returned a bare field-by-field dict with no `"error"` key at all, the one inconsistent response shape in the whole API. See [Error Handling](#error-handling).
- Added `app/utils/util.py` (`encode_token`, `token_required`) and `app/utils/errors.py` (`validation_error_response`), both shared across blueprints rather than duplicated per resource.
- 15 new/updated tests: 10 new in `test_customer_auth.py` (login success/failure, missing-credentials, password never leaking into a response, token-required enforcement on `my-tickets`, malformed/invalid/missing tokens, returning only the logged-in customer's own tickets), plus existing customer-route tests updated for the required `password` field and the new auth requirements on update/delete.

### 2026-09-22: Extended Rate Limiting and Caching Coverage

- Added a route-by-route review of where rate limiting and caching actually make sense, rather than applying the lesson's example to a single route each. See [Rate Limiting & Caching](#rate-limiting--caching) for the full reasoning per resource.
- Rate limited `DELETE /customers/<id>` and `DELETE /mechanics/<id>` to 10 requests per hour per client IP -- deletion is the most destructive route on each resource, so the limit exists to contain a compromised client or a buggy script looping through ids, not to throttle normal use.
- Added a global default limit (`200 per day, 50 per hour`) on the `Limiter` instance itself, applying automatically to every route that has no route-specific `@limiter.limit`, as a backstop against scraping or a runaway polling loop.
- Extended caching to `GET /mechanics/<id>` (single mechanic), using `@cache.memoize()` instead of `@cache.cached()` so each mechanic id gets its own cache entry. `update_mechanic` and `delete_mechanic` now clear both the list cache and that mechanic's own cache entry with `cache.delete_memoized()`.
- Deliberately did **not** extend caching to `Customer` or `ServiceTicket` routes -- both change far too often relative to how often they're read for a cache to pay off. See [Rate Limiting & Caching](#rate-limiting--caching).
- 8 new tests: 4 for the new rate limits (mechanic creation, both delete routes, the global default), 3 for single-mechanic caching and its invalidation on update/delete, and 1 recovering a missing-import bug in `test_mechanic_caching.py` caught via Pylint/Pylance.

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
| Authentication             | JWT (`python-jose`), `werkzeug.security` for password hashing                        |
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
SECRET_KEY=a_long_random_string_used_to_sign_jwts
```

`SECRET_KEY` signs and verifies every JWT issued by `POST /customers/login` (see [Authentication](#authentication)). Treat it like a password -- any long random string works for local development, and it must never be committed.

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

Models match the class-provided ERD exactly, with one deliberate addition:

- **Customer** — `id`, `name`, `email`, `phone`, plus `password_hash` (**not** part of the original ERD -- added for the Token Authentication lesson, since customers need a way to log in; see [Authentication](#authentication))
- **Service_Ticket** — `id`, `vin`, `service_date`, `service_desc`, plus a foreign key to `Customer`
- **Mechanic** — `id`, `name`, `email`, `phone`, `salary` (float)
- **Service_Mechanics** (junction table) — `ticket_id` + `mechanic_id`, linking `Service_Ticket` and `Mechanic`

Relationships:

- **Customer → Service_Ticket**: one-to-many (a customer can have many service tickets, each ticket belongs to exactly one customer)
- **Service_Ticket ↔ Mechanic**: many-to-many, via `Service_Mechanics` (a ticket can require multiple mechanics, a mechanic can work on multiple tickets)

Note: `service_date` is stored as a string (`VARCHAR`), not a `DATE` column, and the junction table's two columns aren't marked as a composite primary key -- both match the ERD and the lesson's own example exactly, rather than "improving" on the given design, since these models are graded against this specific diagram. `password_hash` is the one intentional exception, documented above.

---

## API Endpoints

All request/response bodies are JSON. Routes marked 🔒 require a valid Bearer token -- see [Authentication](#authentication).

### Customer (`/customers`)

| Method    | URL                     | Purpose                                  |
| --------- | ----------------------- | ---------------------------------------- |
| POST      | `/customers`            | Create a customer                        |
| POST      | `/customers/login`      | Log in, receive a JWT                    |
| GET       | `/customers`            | List all customers                       |
| GET       | `/customers/<id>`       | Get one customer                         |
| GET 🔒    | `/customers/my-tickets` | Get the logged-in customer's own tickets |
| PUT 🔒    | `/customers/<id>`       | Update a customer (own account only)     |
| DELETE 🔒 | `/customers/<id>`       | Delete a customer (own account only)     |

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

## Authentication

Token authentication (JWT) protects the `Customer` resource, per the Token Authentication lesson. Which routes require a token was decided per-route, the same way rate limiting and caching were reasoned through, rather than applying the lesson's generic example everywhere.

### The flow

1. **`POST /customers`** creates an account with a `password`. It's hashed with `werkzeug.security.generate_password_hash` before ever touching the database -- the plaintext password is never stored, and `password`/`password_hash` are never included in any response (`CustomerSchema` excludes `password_hash` entirely and marks `password` `load_only`).
2. **`POST /customers/login`** accepts `{"email": "...", "password": "..."}`, verifies it with `check_password_hash`, and returns `{"status": "success", "auth_token": "<jwt>"}` on success. Deliberately returns the same `401` and message whether the email doesn't exist or the password is wrong -- distinguishing the two would let an attacker enumerate which emails are registered.
3. Protected routes are called with `Authorization: Bearer <token>`. The `@token_required` decorator (`app/utils/util.py`) validates the token and passes the token's `customer_id` into the route function -- it's never read from the URL or request body for the logged-in customer's own identity.
4. Tokens expire after 1 hour and are signed with `SECRET_KEY` (from `.env` in development, a fixed test value in `TestingConfig` -- see [Architecture Notes](#architecture-notes)).

### Which routes require a token, and why

| Route                                   | Protected?                    | Why                                                                                                                                                                                                                       |
| --------------------------------------- | ----------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `POST /customers`                       | No                            | Can't require a token before an account exists.                                                                                                                                                                           |
| `POST /customers/login`                 | No                            | Can't require a token to obtain a token.                                                                                                                                                                                  |
| `GET /customers`, `GET /customers/<id>` | No                            | Not scoped to "my own data" -- listing/viewing customers is an admin/staff action, and this system has no staff-login concept. Out of scope for this lesson.                                                              |
| `GET /customers/my-tickets`             | **Yes**                       | The entire point of this route is "show me my own tickets" -- it only makes sense authenticated. `customer_id` comes from the token, never a URL parameter, so there's no id to tamper with in the first place.           |
| `PUT /customers/<id>`                   | **Yes**, plus ownership check | Without this, anyone who knows a customer's id could edit any customer's record. The token's `customer_id` must match the `<id>` in the URL (`403` if not), so a logged-in customer can only ever edit their own account. |
| `DELETE /customers/<id>`                | **Yes**, plus ownership check | Same reasoning as update -- deletion is destructive, and only the account's owner may perform it.                                                                                                                         |
| `Mechanic` and `ServiceTicket` routes   | No                            | The token in this system identifies a _customer_, not a mechanic or staff member. There's no actor here who'd hold a mechanic-scoped token, so applying `@token_required` to those routes wouldn't model anything real.   |

A limited or cached response carries the same status codes and JSON shape described in [Error Handling](#error-handling) above, with one addition specific to auth:

- A missing, malformed, expired, or invalid token returns `401` with `{"error": "..."}` (e.g. `"Token is missing."`, `"Token has expired."`, `"Invalid token."`).
- A valid token belonging to the wrong customer returns `403` with `{"error": "You may only update/delete your own account."}`.

---

## Rate Limiting & Caching

Every route decision below comes down to one question: **how often is this route abused or destructive (for limiting), and how often is its data read versus written (for caching)?**

### Rate limiting

| Route                    | Limit                                      | Why                                                                                                                                                                                                                                                            |
| ------------------------ | ------------------------------------------ | -------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `POST /customers`        | 5 / hour / IP                              | Creation is the write path most open to abuse -- junk records, or probing which emails are already registered. Rejected (400) attempts still count toward the limit, which is what stops that probing.                                                         |
| `POST /mechanics`        | 5 / hour / IP                              | Same reasoning as customer creation. In practice this limit never touches legitimate use -- a real shop only registers a handful of mechanics total.                                                                                                           |
| `POST /customers/login`  | 10 / hour / IP                             | Login is a classic brute-force target -- without a limit, a script could try thousands of password guesses against one email address. Both failed and successful attempts count toward the limit.                                                              |
| `DELETE /customers/<id>` | 10 / hour / IP                             | Deletion is the most destructive route on the resource. The limit guards against a compromised client or a buggy script looping through ids and wiping records, not against a person manually cleaning up a few records.                                       |
| `DELETE /mechanics/<id>` | 10 / hour / IP                             | Same reasoning as customer deletion.                                                                                                                                                                                                                           |
| Every other route        | 200 / day, 50 / hour / IP (global default) | A floor applied to the whole app via `default_limits` on the `Limiter` instance itself, catching routes with no limit of their own (reads, updates, ticket assignment) -- a backstop against scraping or a runaway polling loop, not a throttle on normal use. |

`PUT` (update) routes and `GET` routes carry no route-specific limit: updates don't grow or destroy data, so their damage ceiling is much lower than create or delete, and reads aren't destructive at all. Both still fall under the global default above.

### Caching

| Route                                     | Cached?                             | Why                                                                                                                                                                                                                                                                                                                                                  |
| ----------------------------------------- | ----------------------------------- | ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `GET /mechanics`                          | Yes, 60s                            | The mechanic roster is read constantly (e.g. every time someone assigns a mechanic to a ticket) but written to rarely (mechanics are hired occasionally, not daily). High read-to-write ratio is exactly what caching is for.                                                                                                                        |
| `GET /mechanics/<id>`                     | Yes, 60s, per id (`@cache.memoize`) | Same reasoning as the list. Memoized per `mechanic_id` so `update_mechanic`/`delete_mechanic` can clear one mechanic's entry without invalidating every other mechanic's cached lookup.                                                                                                                                                              |
| `GET /customers` (list/single/my-tickets) | No                                  | Customers are created and updated constantly as new work comes in -- caching would mean invalidating almost as often as it's read, adding complexity for little benefit, on top of holding personal data in memory unnecessarily. `my-tickets` in particular must never be stale: it's what a customer checks to see whether their own work is done. |
| `GET /service-tickets` (list/single)      | No                                  | The most write-heavy resource in the app -- tickets are created and mechanics are assigned/removed throughout the day. A mechanic checking whether they've just been assigned a ticket needs the real answer, not one up to a minute old.                                                                                                            |

Invalidation is explicit, not timeout-only: `create_mechanic` clears the list cache; `update_mechanic` and `delete_mechanic` clear both the list cache and that mechanic's own memoized entry via `cache.delete_memoized()`. A client making a write through the API always sees its own change on the very next `GET` -- the 60-second timeout only matters for a change made outside the API entirely (e.g. directly in MySQL Workbench).

**Known limitation:** caching `GET /mechanics/<id>` also caches a `404` for an id that doesn't exist yet. `create_mechanic` has no way to know in advance which id a new mechanic will be assigned, so it can't invalidate that entry ahead of time. A client that requests an unused id right before it's created could see a stale 404 for up to 60 seconds. Accepted as a narrow edge case rather than adding complexity to solve it.

A limited or cached response carries the same status codes and JSON shape described in [Error Handling](#error-handling) below, with two additions:

- Exceeding any limit returns `429` with `{"error": "Rate limit exceeded", "detail": "..."}`, where `detail` names the specific limit that was hit (e.g. `"5 per 1 hour"` or `"50 per 1 hour"` for the global default).
- Every response includes `X-RateLimit-Limit`, `X-RateLimit-Remaining`, and `X-RateLimit-Reset` headers, so the current state of the limit is visible in Postman without waiting to be blocked.

---

## Error Handling

Every error response in this API shares the same `{"error": "..."}` envelope, no matter which layer produces it -- a global handler, a route's own explicit check, or Marshmallow validation.

- **HTTP-level errors** (unmatched route → 404, wrong HTTP method → 405, malformed JSON body → 400, wrong `Content-Type` header → 415, etc.) are caught by a global handler (`app/error_handlers.py`) and returned as `{"error": "..."}` with the matching status code, instead of Flask's default HTML error page.
- **Unexpected exceptions** in application code are caught by a second global handler, logged server-side, and returned as a generic `{"error": "An unexpected server error occurred."}` with a 500, rather than leaking a raw traceback to the client.
- **Rate limit violations** return `429` with `{"error": "Rate limit exceeded", "detail": "..."}`, where `detail` names the specific limit that was hit (see [Rate Limiting & Caching](#rate-limiting--caching)). Flask checks status-code handlers before class handlers, so this one takes priority over the generic HTTP-level handler above.
- **Validation failures** (a missing or malformed field on create/update/login) return `400` with `{"error": "Validation failed.", "details": {...}}`, where `details` is Marshmallow's own field-by-field message dict, e.g. `{"email": ["Missing data for required field."]}`. Built by a single shared helper, `validation_error_response()` in `app/utils/errors.py`, called from every blueprint's `except ValidationError` block -- previously each route returned Marshmallow's bare `e.messages` dict directly, with no `"error"` key at all, making it the one response shape in the API that didn't match the rest. Standardizing this was a direct response to instructor feedback asking for more comprehensive, consistent error handling.
- **Authentication failures** (missing/expired/invalid token) return `401`; an authenticated-but-wrong-customer request returns `403`. See [Authentication](#authentication).
- **Expected application-level failures** with their own specific messages -- `{"error": "Customer not found."}`, `{"error": "Email already associated with an account."}`, `{"error": "Mechanic is already assigned to this ticket."}`, and so on -- are returned directly by each route's own logic. These never touch the global handlers at all, since they're ordinary return values, not raised exceptions.

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
    utils/
      __init__.py
      util.py                   # encode_token(), token_required decorator
      errors.py                 # validation_error_response() -- shared 400 envelope
    models/
      __init__.py
      customer.py                # includes password_hash (see Authentication)
      mechanic.py
      service_ticket.py
      service_mechanics.py       # service_mechanics junction table
    blueprints/
      __init__.py
      customer/
        __init__.py               # creates and registers the Customer blueprint
        routes.py                 # CRUD + login + my-tickets for /customers
        schemas.py                # CustomerSchema, LoginSchema
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
    conftest.py                 # shared pytest fixtures, payload/login helpers
    test_customer_model.py
    test_mechanic_model.py
    test_service_ticket_model.py
    test_customer_routes.py
    test_mechanic_routes.py
    test_service_ticket_routes.py
    test_customer_auth.py       # login, token_required, my-tickets
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
- `limiter = Limiter(..., default_limits=[...])` sets its global floor on the constructor rather than passing `app=app` directly, matching the rest of this project's `init_app()`-based wiring: the instance is created without an app in `extensions.py` and bound to the real app later, inside `create_app()`.
- `get_mechanic` (single-mechanic lookup) uses `@cache.memoize()` instead of `@cache.cached()`. `memoize` keys the cache entry by the function's arguments automatically, so each `mechanic_id` gets its own independent entry -- letting `update_mechanic`/`delete_mechanic` invalidate exactly one mechanic's cached lookup via `cache.delete_memoized(get_mechanic, mechanic_id)` without disturbing any other mechanic's cached data.
- `SECRET_KEY` signs and verifies JWTs via `current_app.config["SECRET_KEY"]` inside `encode_token()`/`token_required()`, rather than a hardcoded constant -- this guarantees a token can never be encoded with a different key than it's decoded with, and keeps the real key out of source control. `TestingConfig` sets a fixed, non-secret value so the test suite never depends on `.env` existing, which matters for CI, which has no `.env` file at all.
- `CustomerSchema` excludes `password_hash` entirely (`Meta.exclude`) and adds a non-model `password` field marked `load_only=True` -- accepted on input, hashed by the route, never serialized back into a response even by accident. `LoginSchema` is derived the same way, restricted to just `email` and `password` via `Meta.fields`.
- Validation-error formatting lives in one place, `app/utils/errors.py`, rather than being repeated in every blueprint's `except ValidationError` block -- so every resource's 400 response is guaranteed to share the same shape, and a future format change only needs to happen once.

---

## Testing

### Automated tests

Each model has its own test file, written alongside the model as it was built, plus a matching route test file for its HTTP endpoints:

- **`test_customer_model.py`** / **`test_customer_routes.py`** — model-level creation and unique-email enforcement; every `/customers` endpoint including duplicate-email, missing-field, and missing-password rejection, 404s for bad ids, and the auth/ownership rules on update and delete.
- **`test_customer_auth.py`** — login with valid/invalid/missing credentials (and that the "email not found" and "wrong password" cases return the identical response, so a client can't enumerate registered emails); that a password never appears in any response; `token_required` enforcement (missing, malformed, and invalid tokens) on `GET /customers/my-tickets`; and that `my-tickets` returns only the logged-in customer's own tickets, never another customer's.
- **`test_mechanic_model.py`** / **`test_mechanic_routes.py`** — model-level creation and the many-to-many relationship to tickets; every `/mechanics` endpoint including the extra-credit get-one route.
- **`test_service_ticket_model.py`** / **`test_service_ticket_routes.py`** — model-level creation and the many-to-many relationship to mechanics; every `/service-tickets` endpoint including assign/remove-mechanic edge cases (duplicate assignment, removing an unassigned mechanic, ticket/mechanic not found).
- **`test_rate_limiting.py`** — confirms `POST /customers` and `POST /mechanics` each allow 5 requests per hour then return 429; that `DELETE /customers/<id>` and `DELETE /mechanics/<id>` each allow 10 requests per hour then return 429 (counting even auth failures, since repeated attempts against the same guessed id are exactly what the limit guards against); that rejected requests still count toward a limit; that a limit on one route doesn't block others; that rate-limit headers are present; that the global default limit applies to a route with no route-specific limit of its own; and that the default test config leaves rate limiting off entirely.
- **`test_mechanic_caching.py`** — confirms `GET /mechanics` and `GET /mechanics/<id>` are both served from cache (a direct database insert or edit the API never saw stays invisible until the cache clears); that caching is off by default in tests; and that create, update, and delete on `/mechanics` each immediately refresh the relevant cache entries, including the single-mechanic cache correctly returning 404 right after a delete.
- **`test_error_handlers.py`** — confirms unmatched routes, wrong HTTP methods, malformed JSON, and wrong `Content-Type` all return consistent JSON rather than Flask's default HTML error pages.

Tests run against a temporary in-memory SQLite database (via `TestingConfig`), never the real MySQL database — so the suite is fast and never at risk of touching or corrupting real data.

Run the full suite:

```powershell
python -m pytest -v
```

Currently: **83 tests, all passing.**

### Testing with Postman

In addition to the automated test suite, every endpoint was also manually verified against the real running app and the real MySQL database, using Postman. The saved requests are exported as `Mechanic_Shop_API.postman_collection.json` in the project root.

To use it:

1. Open Postman.
2. Click **Import** and select `Mechanic_Shop_API.postman_collection.json`.
3. Make sure the app is running locally (`python run.py`).
4. Open the `Mechanic Shop API` collection and send any request — each one is pre-filled with the correct method, URL, and (where needed) a sample JSON body. For protected routes, log in via `POST /customers/login` first and copy the returned `auth_token` into the request's `Authorization` header as `Bearer <token>`.

See [API Endpoints](#api-endpoints) above for the full list covered, and [Authentication](#authentication) for which routes need a token.

---

## CI

`.github/workflows/ci.yml` runs on every push and pull request to `main`: installs dependencies from `requirements.txt`, runs the full pytest suite, then runs Pylint. Because tests use an in-memory SQLite database rather than a real MySQL connection, this workflow needs no database service or secrets configured at all -- `TestingConfig` sets its own fixed `SECRET_KEY`, so the workflow never needs the real one either.

This wasn't required by the assignment -- it's carried over from CI/CD coursework on a prior project. Unlike that project, this API isn't deployed anywhere, so there's no CD (deployment) stage here, which is also why this file is named `ci.yml` rather than `main.yml`.

---

## Submission Checklist

- [x] Blueprints registered for `customer`, `mechanic`, and `service_ticket`, each with its own `url_prefix`
- [x] Full CRUD implemented for `Customer` and `Mechanic`; `ServiceTicket` create/list/assign-mechanic/remove-mechanic (no update/delete, by design)
- [x] Marshmallow schemas validate and serialize every resource
- [x] Token authentication: login issues a JWT; `my-tickets`, update, and delete all require a valid token, with update/delete additionally enforcing account ownership
- [x] Rate limiting: 5/hour on customer/mechanic creation, 10/hour on customer login and customer/mechanic deletion, 200/day + 50/hour global default on every other route
- [x] Caching: `GET /mechanics` and `GET /mechanics/<id>` cached (60s) with explicit invalidation on create/update/delete
- [x] Every error response, including validation failures, shares one consistent `{"error": ...}` envelope
- [x] Postman collection included in the repo and covers every endpoint
- [x] 83 automated tests passing (`python -m pytest -v`)
- [x] Pylint clean (`python -m pylint app tests config.py`)
- [x] CI workflow passing on GitHub Actions
