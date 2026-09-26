# Mechanic Shop Management System

![Python](https://img.shields.io/badge/Python-3776AB?logo=python&logoColor=white&style=flat-square)
![Flask](https://img.shields.io/badge/Flask-000000?logo=flask&logoColor=white&style=flat-square)
![SQLAlchemy](https://img.shields.io/badge/SQLAlchemy-D71F00?logoColor=white&style=flat-square)
![Marshmallow](https://img.shields.io/badge/Marshmallow-black?logoColor=white&style=flat-square)
![MySQL](https://img.shields.io/badge/MySQL-4479A1?logo=mysql&logoColor=white&style=flat-square)
![JWT](https://img.shields.io/badge/JWT-black?logo=jsonwebtokens&logoColor=white&style=flat-square)
![Faker](https://img.shields.io/badge/Faker-FF6E42?style=flat-square)
![pytest](https://img.shields.io/badge/pytest-0A9EDC?logo=pytest&logoColor=white&style=flat-square)
![Postman](https://img.shields.io/badge/Postman-FF6C37?logo=postman&logoColor=white&style=flat-square)
![Pylint](https://img.shields.io/badge/Pylint-enabled-brightgreen?style=flat-square)
![GitHub Actions](https://img.shields.io/badge/GitHub_Actions-2088FF?logo=githubactions&logoColor=white&style=flat-square)

A Flask + SQLAlchemy + MySQL backend for a mechanic shop, with role-based JWT authentication (customer, mechanic, manager), a real service-ticket lifecycle (status and cost), Marshmallow-validated CRUD, and a Faker-driven seed script -- built on the Application Factory pattern. Built for the "Database Design and Planning with ERDs," "SQLAlchemy Relationships," "Marshmallow Schemas & CRUD Endpoints," "Application Factory Pattern," "Rate Limiting and Caching," "Token Authentication," and "Advanced SQLAlchemy Queries" course modules.

**Author:** Kathy Booth (with contributions from Claude and GitHub Copilot)

---

## Table of Contents

- [Changelog](#changelog)
- [Tech Stack](#tech-stack)
- [Getting Started](#getting-started)
- [Database Setup](#database-setup)
- [Seed Data](#seed-data)
- [Entity-Relationship Diagram](#entity-relationship-diagram)
- [Roles & Authorization](#roles--authorization)
- [API Endpoints](#api-endpoints)
- [Authentication](#authentication)
- [Rate Limiting & Caching](#rate-limiting--caching)
- [Pagination](#pagination)
- [Error Handling](#error-handling)
- [Project Structure](#project-structure)
- [Architecture Notes](#architecture-notes)
- [Testing](#testing)
- [CI](#ci)
- [Future Extensions](#future-extensions)

---

## Changelog

### 2026-09-25: Role-Based Authorization, Ticket Lifecycle, Sorting, and Pagination

This is the largest single change to the project so far -- a deliberate redesign that goes well beyond this lesson's minimum requirements, aimed at making the API reflect how a real shop would actually operate rather than leaving every action open to everyone.

- **Mechanic authentication and roles.** `Mechanic` gained `password_hash` and `role` (`"mechanic"` or `"manager"`). `POST /mechanics/login` mirrors customer login. Unlike `Customer`, a mechanic account cannot self-register -- only an existing manager can create one, closing the "any mechanic could act with full privileges" gap that motivated this whole redesign in the first place. See [Roles & Authorization](#roles--authorization) for the full reasoning behind every route's access level.
- **Service ticket lifecycle.** `ServiceTicket` gained `status` (`Pending` → `In Progress` → `Completed` → `Paid` → `Picked Up`) and `cost` (the estimate given up front, editable later). Any logged-in mechanic can update a ticket's status -- that's the one action every mechanic performs as part of doing the actual work. Editing a ticket's description or cost, and assigning or removing mechanics (single or bulk), are manager-only.
- **`service_date` is now a real `Date` column** (was `VARCHAR`), and **`salary`/`cost` use `Decimal`, not float** -- see [Architecture Notes](#architecture-notes) for why, and for the correction to this README's own earlier (mistaken) claim that the class ERD required exact type fidelity.
- **Bulk mechanic assignment.** `PUT /service-tickets/<id>/edit` takes `add_ids`/`remove_ids` and applies both in one request. Deliberately idempotent on redundancy (adding an already-assigned mechanic, or removing one who isn't assigned, is silently skipped) -- unlike the single-action `assign-mechanic`/`remove-mechanic` routes, which still reject exact redundancy as an error. A mechanic id that doesn't exist at all is still a real `404` either way.
- **Salary privacy.** A regular mechanic can view their own full profile (including salary) but not anyone else's, and cannot see the full roster at all (`GET /mechanics` is manager-only now, since it includes everyone's pay). The three sorting/insight endpoints below are open to any mechanic but never include salary in their response.
- **Sorting/insight endpoints**, all mechanic-authenticated, all supporting `?order=asc` to reverse the default descending sort:
  - `GET /mechanics/most-tickets` -- total tickets ever worked
  - `GET /mechanics/open-tickets` -- currently open tickets (Pending/In Progress/Completed)
  - `GET /mechanics/closed-tickets` -- closed tickets (Paid/Picked Up)
- **Pagination on `GET /customers`.** `?page`/`?page_size` (default page size 7, capped at 50), wrapped in an object (`{"customers": [...], "total": ..., "page": ..., "page_size": ..., "total_pages": ...}`) instead of a bare array -- see [Pagination](#pagination).
- **`seed.py`**, a new standalone script using Faker to wipe and repopulate the database with a manager, several mechanics (including three intentionally unused ones for testing deletion), a dozen-plus customers, and 33 tickets spread across every status. See [Seed Data](#seed-data).
- **68 new/updated tests** across mechanic auth, mechanic routes, mechanic sorting, service ticket routes, customer routes (pagination), rate limiting, and caching.

### 2026-09-23: Token Authentication and Standardized Error Handling

- Added JWT-based token authentication for the `Customer` resource. `POST /customers/login` exchanges an email and password for a token; `GET /customers/my-tickets`, `PUT /customers/<id>`, and `DELETE /customers/<id>` all require a valid token, and the latter two additionally verify the token's customer matches the id in the URL.
- `Customer` gained a `password_hash` column, hashed with `werkzeug.security` and never returned in any response. This is **not** part of the class-provided ERD -- documented as a deliberate, necessary extension for this lesson.
- Standardized every validation-failure response across all three resources to the same `{"error": "...", "details": {...}}` envelope every other error in this API already used -- closing a real gap flagged in instructor feedback on the previous submission ("comprehensive error handling and custom error messages").
- Added `app/utils/util.py` (`encode_token`, `token_required`) and `app/utils/errors.py` (`validation_error_response`), both shared across blueprints rather than duplicated per resource.
- 15 new/updated tests.

### 2026-09-22: Extended Rate Limiting and Caching Coverage

- Rate limited `DELETE /customers/<id>` and `DELETE /mechanics/<id>` to 10 requests per hour per client IP -- deletion is the most destructive route on each resource.
- Added a global default limit (`200 per day, 50 per hour`) on the `Limiter` instance itself, applying automatically to every route that has no route-specific `@limiter.limit`.
- Extended caching to `GET /mechanics/<id>` (single mechanic), using `@cache.memoize()` instead of `@cache.cached()`. (This was later removed entirely in the 2026-09-25 update, once the route also required authentication -- see [Architecture Notes](#architecture-notes).)
- 8 new tests.

### 2026-09-21: Rate Limiting and Caching

- Added Flask-Limiter, rate limiting `POST /customers` to 5 requests per hour per client IP.
- Added Flask-Caching, caching `GET /mechanics` for 60 seconds, with explicit invalidation on every write.
- Config split by environment: `DevelopmentConfig` uses `SimpleCache` and a `memory://` rate-limit store; `TestingConfig` uses `NullCache` and disables rate limiting entirely.
- 10 new tests.

### 2026-09-16: Global Error Handling, CI, and Dependency Fix

- Added global error handlers (`app/error_handlers.py`) so unmatched routes, wrong HTTP methods, and malformed/missing JSON bodies all return consistent JSON instead of Flask's default HTML error pages.
- Added `.github/workflows/ci.yml`: runs the full test suite and Pylint on every push/PR.
- Fixed a real gap in `requirements.txt` that would have broken a fresh install with `ModuleNotFoundError`.
- 4 new tests.

### 2026-09-15: Mechanic and ServiceTicket Resources, Application Factory Refactor

- Added full CRUD for `Mechanic` and routes for `ServiceTicket` (create, get-all, get-one, assign/remove-mechanic).
- Reorganized into the Application Factory pattern's blueprint structure.
- 24 new tests.

### 2026-09-14: ERD Correction

- Rebuilt all three models and the junction table to match the class-provided ERD exactly, after an earlier draft diverged from it.

### 2026-09-14: Initial Models & Project Setup

- Set up the project as a Flask application using the app factory pattern, with separate MySQL (development) and SQLite (testing) configs.
- Built `Customer`, `Mechanic`, and `ServiceTicket` models plus the junction table.

---

## Tech Stack

| Layer                      | Technology                                                                           |
| -------------------------- | ------------------------------------------------------------------------------------ |
| Web framework              | Flask (Application Factory pattern)                                                  |
| ORM                        | Flask-SQLAlchemy (SQLAlchemy 2.0 `Mapped`/`mapped_column` style)                     |
| Serialization / validation | Flask-Marshmallow, marshmallow-sqlalchemy                                            |
| Database                   | MySQL (via `mysql-connector-python`)                                                 |
| Authentication             | JWT (`python-jose`), `werkzeug.security` for password hashing, role-based access     |
| Rate limiting              | Flask-Limiter (in-memory store)                                                      |
| Caching                    | Flask-Caching (`SimpleCache` in development, `NullCache` in tests)                   |
| Seed data                  | Faker                                                                                |
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
MANAGER_EMAIL=manager@shop.com
MANAGER_PASSWORD=choose_your_own_password
```

`SECRET_KEY` signs and verifies every JWT (customer and mechanic alike). `MANAGER_EMAIL`/`MANAGER_PASSWORD` are read only by `seed.py`, to create the one manager account you'll actually want to remember the login for (see [Seed Data](#seed-data)). Treat all of these like passwords -- never commit real values.

### Run locally

```powershell
python run.py
```

This creates every table defined by the models (if they don't already exist) in the real MySQL database configured above, then starts the Flask dev server.

---

## Database Setup

1. Open MySQL Workbench and connect to your local MySQL instance.
2. Run `CREATE DATABASE mechanic_shop;` (or whatever name you used for `DB_NAME` above).
3. Run `python run.py` once to create all tables, **or** run `python seed.py` to create the tables _and_ populate them with realistic demo data in one step (recommended -- see [Seed Data](#seed-data)).

---

## Seed Data

```powershell
python seed.py
```

This **drops and recreates every table**, then populates the database with:

- **1 manager** -- credentials from `.env` (`MANAGER_EMAIL`/`MANAGER_PASSWORD`), since this is the account you're most likely to log in as by hand.
- **4 core mechanics** -- deliberately uneven ticket loads (one busy, one moderate, one light, one with zero tickets, as if freshly hired), so the sorting endpoints have something real to show.
- **3 extra mechanics** -- never assigned to any ticket, safe to `DELETE` via the API without disturbing anything else. Meant specifically for manually testing `delete_mechanic`.
- **12 core customers**, each with at least one ticket.
- **2 extra customers** with no tickets -- safe to `DELETE`, same purpose as the extra mechanics.
- **33 service tickets**, spread across all five statuses, with VINs generated to satisfy the same ISO-3779-style validator the API itself enforces (Faker has no built-in VIN provider).

**Password scheme (local demo data only, never for production):** every seeded customer's password is `customerpassword<id>`, and every seeded regular mechanic's password is `mechanicpassword<id>`, where `<id>` is that record's real database id -- so looking up an id in MySQL Workbench tells you its password. The manager account is the one exception, using whatever you set in `.env`, since it's the account meant for you to actually remember.

Running `seed.py` again wipes and rebuilds from scratch -- it does not merge with or preserve anything added since the last run, including data created by hand through Postman. This is intentional: the predictable password scheme only holds if ids are predictable, which requires starting from an empty database every time.

---

## Entity-Relationship Diagram

Models started from the class-provided ERD, with several deliberate departures made once we confirmed nothing in the assignment actually requires exact type fidelity to it (see [Architecture Notes](#architecture-notes) for that story):

- **Customer** -- `id`, `name`, `email`, `phone`, plus `password_hash` (not in the original ERD -- added for customer login)
- **Mechanic** -- `id`, `name`, `email`, `phone`, `salary` (now `Decimal`, was `FLOAT`), plus `password_hash` and `role` (not in the original ERD -- added for mechanic login and role-based authorization)
- **Service_Ticket** -- `id`, `vin`, `service_date` (now a real `Date`, was `VARCHAR`), `service_desc`, plus a foreign key to `Customer`, plus `status` and `cost` (not in the original ERD -- added for the ticket lifecycle and pricing)
- **Service_Mechanics** (junction table) -- `ticket_id` + `mechanic_id`, linking `Service_Ticket` and `Mechanic`

Relationships:

- **Customer → Service_Ticket**: one-to-many
- **Service_Ticket ↔ Mechanic**: many-to-many, via `Service_Mechanics`

---

## Roles & Authorization

Two roles exist on `Mechanic`: `"mechanic"` and `"manager"`. There is no third tier, and no concept of a software-vendor-level "admin" spanning multiple shops -- see [Future Extensions](#future-extensions) for that idea, deliberately left unbuilt.

Every route's access level was reasoned through individually, the same way rate limiting and caching were in earlier lessons, rather than gating everything uniformly:

| Action                                                                 | Who                                            | Why                                                                                                                                                                        |
| ---------------------------------------------------------------------- | ---------------------------------------------- | -------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| Create a mechanic account                                              | Manager only                                   | Unlike `Customer`, staff accounts cannot self-register. Letting any mechanic create another mechanic (or promote themselves) would defeat the whole point of having roles. |
| View the full mechanic roster (with salary)                            | Manager only                                   | Salary is sensitive; a regular mechanic has no legitimate reason to see everyone's pay.                                                                                    |
| View a single mechanic's profile (with salary)                         | The mechanic themselves, or a manager (anyone) | A mechanic can always see their own salary; only a manager can look up someone else's.                                                                                     |
| Update or delete a mechanic account                                    | Manager only                                   | Roster changes -- including salary and role -- are a management decision.                                                                                                  |
| Create a service ticket                                                | Manager only                                   | Creation sets `cost` and `service_desc` up front, both otherwise manager-controlled everywhere else; gating creation the same way keeps that consistent.                   |
| View tickets (list, single, or "my tickets")                           | Any logged-in mechanic                         | Staff need visibility into the queue; "my tickets" is scoped to what that mechanic is personally assigned to.                                                              |
| Edit a ticket's description/cost                                       | Manager only                                   | Same reasoning as ticket creation.                                                                                                                                         |
| Update a ticket's status                                               | Any logged-in mechanic                         | This is the one action every mechanic performs as part of doing the actual work, not a management decision.                                                                |
| Assign/remove mechanics (single or bulk)                               | Manager only                                   | Assigning staff to work is a management decision.                                                                                                                          |
| Sorting/insight endpoints (most-tickets, open-tickets, closed-tickets) | Any logged-in mechanic                         | Useful to everyone for gauging workload; response never includes salary.                                                                                                   |

A customer's own authorization is unchanged from the previous lesson: they can view their own tickets (`GET /customers/my-tickets`, read-only, status visible but not editable) and manage their own account, and nothing else.

---

## API Endpoints

All request/response bodies are JSON. Routes marked 🔒 require a valid Bearer token (customer or mechanic, as noted); 👔 marks manager-only routes.

### Customer (`/customers`)

| Method    | URL                     | Purpose                                   |
| --------- | ----------------------- | ----------------------------------------- |
| POST      | `/customers`            | Create (register) a customer              |
| POST      | `/customers/login`      | Log in, receive a JWT                     |
| GET       | `/customers`            | List customers, **paginated** (see below) |
| GET       | `/customers/<id>`       | Get one customer                          |
| GET 🔒    | `/customers/my-tickets` | Get the logged-in customer's own tickets  |
| PUT 🔒    | `/customers/<id>`       | Update a customer (own account only)      |
| DELETE 🔒 | `/customers/<id>`       | Delete a customer (own account only)      |

### Mechanic (`/mechanics`)

| Method    | URL                         | Purpose                                              |
| --------- | --------------------------- | ---------------------------------------------------- |
| POST 👔   | `/mechanics`                | Create a mechanic                                    |
| POST      | `/mechanics/login`          | Log in, receive a JWT (carries the mechanic's role)  |
| GET 👔    | `/mechanics`                | List all mechanics, including salary                 |
| GET 🔒    | `/mechanics/<id>`           | Get one mechanic -- own profile, or any if manager   |
| GET 🔒    | `/mechanics/most-tickets`   | Mechanics sorted by total tickets worked (`?order=`) |
| GET 🔒    | `/mechanics/open-tickets`   | Mechanics sorted by open ticket count (`?order=`)    |
| GET 🔒    | `/mechanics/closed-tickets` | Mechanics sorted by closed ticket count (`?order=`)  |
| PUT 👔    | `/mechanics/<id>`           | Update a mechanic                                    |
| DELETE 👔 | `/mechanics/<id>`           | Delete a mechanic                                    |

### Service Ticket (`/service-tickets`)

| Method  | URL                                                   | Purpose                                            |
| ------- | ----------------------------------------------------- | -------------------------------------------------- |
| POST 👔 | `/service-tickets`                                    | Create a service ticket                            |
| GET 🔒  | `/service-tickets`                                    | List all service tickets                           |
| GET 🔒  | `/service-tickets/my-tickets`                         | Tickets the logged-in mechanic is assigned to      |
| GET 🔒  | `/service-tickets/<id>`                               | Get one service ticket                             |
| PUT 👔  | `/service-tickets/<id>`                               | Update description and/or cost                     |
| PUT 🔒  | `/service-tickets/<id>/status`                        | Update status (any mechanic)                       |
| PUT 👔  | `/service-tickets/<id>/assign-mechanic/<mechanic_id>` | Assign one mechanic to a ticket                    |
| PUT 👔  | `/service-tickets/<id>/remove-mechanic/<mechanic_id>` | Remove one mechanic from a ticket                  |
| PUT 👔  | `/service-tickets/<id>/edit`                          | Bulk add/remove mechanics (`add_ids`/`remove_ids`) |

Deliberately no full `PUT`/`DELETE` for the ticket resource itself -- only the scoped detail/status/mechanic routes above -- so a completed or in-progress service record is never silently overwritten or erased wholesale.

---

## Authentication

Two independent JWT flows exist, both signed with the same `SECRET_KEY` but distinguished by a `"type"` claim in the token payload (`"customer"` or `"mechanic"`) -- without that claim, a customer's own valid token could potentially be presented to a mechanic-only route (or vice versa) if their ids happened to collide, since a JWT's signature alone says nothing about which kind of account issued it.

### Customer flow

1. `POST /customers` registers an account with a hashed password.
2. `POST /customers/login` exchanges email/password for a token (`encode_token`).
3. `token_required` validates the token and passes the customer's own id into the route.

### Mechanic flow

1. `POST /mechanics` (manager-only) creates a mechanic account with a role and a hashed password.
2. `POST /mechanics/login` exchanges email/password for a token that also carries the mechanic's role (`encode_mechanic_token`).
3. `mechanic_token_required` validates the token and passes the mechanic's id and role into the route.
4. `manager_required` wraps `mechanic_token_required`, additionally checking that the role is `"manager"` -- a valid, unexpired mechanic token is still correctly rejected from a manager-only route if its role doesn't match.

Both logins return the identical `401` message for a wrong password and an unregistered email, so a client can never use the response to enumerate which accounts exist.

A limited, cached, or authenticated response carries the same status codes and JSON shape described in [Error Handling](#error-handling), with these additions:

- A missing, malformed, expired, or wrong-type token returns `401` with `{"error": "..."}`.
- A structurally valid token of the wrong role or wrong owner returns `403` with `{"error": "..."}`.

---

## Rate Limiting & Caching

Every route decision comes down to one question: **how often is this route abused or destructive (for limiting), and how often is its data read versus written (for caching)?**

### Rate limiting

| Route                                               | Limit                                      | Why                                                                                                                                                              |
| --------------------------------------------------- | ------------------------------------------ | ---------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `POST /customers`                                   | 5 / hour / IP                              | Creation is the write path most open to abuse. Rejected (400) attempts still count toward the limit, which is what stops probing for registered emails.          |
| `POST /mechanics`                                   | 5 / hour / IP                              | Same reasoning, though it never touches legitimate use -- a real shop only registers a handful of mechanics total, and only a manager can even reach this route. |
| `POST /customers/login` / `POST /mechanics/login`   | 10 / hour / IP                             | Login is a classic brute-force target. Both failed and successful attempts count toward the limit.                                                               |
| `DELETE /customers/<id>` / `DELETE /mechanics/<id>` | 10 / hour / IP                             | Deletion is the most destructive route on either resource.                                                                                                       |
| Every other route                                   | 200 / day, 50 / hour / IP (global default) | A floor applied via `default_limits` on the `Limiter` instance itself, catching every route with no limit of its own.                                            |

### Caching

| Route                                                               | Cached?         | Why                                                                                                                                                                                                                                                                                                                                                                                                                                                            |
| ------------------------------------------------------------------- | --------------- | -------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `GET /mechanics`                                                    | Yes, 60s        | The roster is read constantly but written to rarely (mechanics are hired occasionally, not daily). High read-to-write ratio.                                                                                                                                                                                                                                                                                                                                   |
| `GET /mechanics/<id>`                                               | **No, removed** | Once this route also requires authentication, `@cache.memoize` would key each cache entry by the _requesting_ mechanic's id and role too -- every different requester caching their own separate copy of the same lookup, which `cache.delete_memoized()` could no longer reliably clear on update/delete. Given this is now authenticated internal traffic rather than public, high-volume traffic, the caching benefit no longer outweighed that complexity. |
| `GET /customers`, `GET /service-tickets`, and the sorting endpoints | No              | Written to too often (customers and tickets are created/updated constantly; the sorting endpoints depend on ticket-assignment activity across the whole shop) for a timed cache to stay accurate.                                                                                                                                                                                                                                                              |

Authentication is always the _outer_ decorator on a cached route (`@manager_required` above `@cache.cached`), never the reverse: Flask-Caching keys its cache by the request path, not by who's asking, so if caching ran first, one authenticated request's response could be served to a later, completely unauthenticated one hitting the same path.

---

## Pagination

`GET /customers` is paginated:

```
GET /customers?page=2&page_size=10
```

- `page` defaults to `1`; invalid or missing values fall back to the default rather than erroring.
- `page_size` defaults to `7`, and is capped at `50` regardless of what's requested, so a client can't pull the entire table in one call.
- A `page` past the last real page returns an **empty list**, not a `404` -- the request itself is valid, there's just nothing there.

Response shape:

```json
{
    "customers": [ ... ],
    "total": 14,
    "page": 1,
    "page_size": 7,
    "total_pages": 2
}
```

No other list route is paginated -- the mechanic roster and ticket list are both expected to stay small enough in this project's scope that pagination wouldn't add real value, while `/customers` was the one the assignment specifically asked for.

---

## Error Handling

Every error response in this API shares the same `{"error": "..."}` envelope, no matter which layer produces it.

- **HTTP-level errors** (404, 405, 400 malformed JSON, 415, etc.) are caught by a global handler and returned as `{"error": "..."}`.
- **Unexpected exceptions** are caught, logged server-side, and returned as a generic `{"error": "An unexpected server error occurred."}` with a 500.
- **Rate limit violations** return `429` with `{"error": "Rate limit exceeded", "detail": "..."}`.
- **Validation failures** return `400` with `{"error": "Validation failed.", "details": {...}}`, where `details` is Marshmallow's own field-by-field message dict -- built by a single shared helper, `validation_error_response()`, called from every blueprint.
- **Authentication/authorization failures** return `401` (missing/invalid/expired/wrong-type token) or `403` (valid token, wrong owner or wrong role).
- **Expected application-level failures** with their own specific messages (`"Customer not found."`, `"Email already associated with an account."`, `"Mechanic is already assigned to this ticket."`, etc.) are returned directly by each route.

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
  seed.py                     # wipes + repopulates the database with Faker demo data
  Mechanic_Shop_API.postman_collection.json
  .github/
    workflows/
      ci.yml
  app/
    __init__.py                # app factory (create_app())
    extensions.py               # shared db / ma / limiter / cache instances
    error_handlers.py           # global JSON error handlers
    utils/
      __init__.py
      util.py                   # encode_token/encode_mechanic_token, token_required,
                                 # mechanic_token_required, manager_required
      errors.py                 # validation_error_response() -- shared 400 envelope
    models/
      __init__.py
      customer.py                # includes password_hash
      mechanic.py                 # includes password_hash, role; salary is Decimal
      service_ticket.py           # includes status, cost; service_date is Date
      service_mechanics.py        # junction table
    blueprints/
      __init__.py
      customer/
        __init__.py
        routes.py                 # CRUD + login + my-tickets + pagination
        schemas.py                # CustomerSchema, LoginSchema
      mechanic/
        __init__.py
        routes.py                 # CRUD + login + sorting endpoints, role-gated
        schemas.py                # MechanicSchema, LoginSchema, VALID_ROLES
      service_ticket/
        __init__.py
        routes.py                 # CRUD + status/edit/bulk-edit, role-gated
        schemas.py                # ServiceTicketSchema + 3 supporting schemas,
                                   # VALID_STATUSES/OPEN_STATUSES/CLOSED_STATUSES
  tests/
    __init__.py
    conftest.py                 # fixtures, payload helpers, manager/mechanic bootstrap
    test_customer_model.py
    test_mechanic_model.py
    test_service_ticket_model.py
    test_customer_routes.py     # includes pagination tests
    test_mechanic_routes.py
    test_mechanic_auth.py
    test_mechanic_sorting.py
    test_service_ticket_routes.py
    test_customer_auth.py
    test_rate_limiting.py
    test_mechanic_caching.py
    test_error_handlers.py
```

---

## Architecture Notes

### On the ERD-fidelity principle -- a correction

An earlier version of this README justified matching the class-provided ERD's exact column types (`service_date` as `VARCHAR`, `salary` as `FLOAT`) by claiming these models were "graded against this specific diagram." On review of the actual assignment instructions, **that was never true** -- the assignment specifies required fields, routes, and schemas, but says nothing about strict type fidelity to the diagram. That framing was a design principle introduced along the way, not an instructor requirement, and this README previously stated it inaccurately. Having confirmed that, `service_date` was changed to a real `Date` column and `salary`/`cost` to `Decimal`, both textbook-correct choices this project can now make freely, without conflating a design preference with a grading constraint.

### Why not a single `app.py`, like the lesson shows?

Wrapping app creation in `create_app()` (the Application Factory pattern) means each test can get a fresh, fully isolated app backed by an in-memory database, without ever touching real data -- a single module-level `app = Flask(__name__)` gets created once, permanently wired to the real database, the moment the file is imported.

### Blueprints, one folder per resource

Each resource's routes and schema live together in their own folder under `app/blueprints/`. Each blueprint's `__init__.py` creates the `Blueprint` object, then imports its own `routes.py` at the very bottom, avoiding a circular import.

### Provider-style separation

- `app/extensions.py` holds `db`, `ma`, `limiter`, and `cache`, kept separate from `app/__init__.py` to avoid a circular import between model/schema files and the app factory.
- `app/utils/util.py` holds both token flows and all three access-control decorators, so every blueprint imports from one place rather than duplicating auth logic.
- **`manager_required`'s inner wrapper parameter is named `requester_id`, not `mechanic_id`** -- several routes it decorates (`update_mechanic`, `delete_mechanic`, `assign_mechanic`, `remove_mechanic`) have a URL parameter _also_ named `mechanic_id`. Flask passes URL parameters as keyword arguments, so if the wrapper's own parameter shared that name, Python would raise "got multiple values for argument" the moment both tried to bind to the same name -- a real bug caught while writing this feature's tests, not merely a style choice.
- `cache = Cache()` in `extensions.py` is created with no config, so `TestingConfig` can override the backend (`SimpleCache` vs `NullCache`) through `app.config` rather than the constructor overriding it.
- `limiter = Limiter(..., default_limits=[...])` sets its global floor on the constructor, matching this project's `init_app()`-based wiring elsewhere.
- `get_mechanic` (single-mechanic lookup) is intentionally _not_ cached, once it also required authentication -- see [Rate Limiting & Caching](#rate-limiting--caching) for the full reasoning.
- `ServiceTicketSchema`, `MechanicSchema` and friends declare `salary`/`cost` as `fields.Decimal(as_string=True, places=2, ...)` -- `Decimal` values aren't JSON-serializable by Flask's default encoder, so Marshmallow converts them to a fixed-precision string (`"450.00"`) on the way out, while still accepting an int/float/string on the way in.
- `VALID_ROLES`, `VALID_STATUSES`, `OPEN_STATUSES`, and `CLOSED_STATUSES` are each defined once, in their owning schema module, and imported wherever else they're needed (e.g. the mechanic blueprint imports the status lists to compute open/closed ticket counts) -- so the set of valid values and the routes that depend on it can never drift out of sync.

---

## Testing

### Automated tests

Run the full suite:

```powershell
python -m pytest -v
```

Currently: **120 tests, all passing.**

- **`test_customer_model.py`** / **`test_customer_routes.py`** -- creation, uniqueness, auth/ownership on update/delete, and pagination on the list route.
- **`test_customer_auth.py`** -- login, password-never-leaked, `my-tickets` token enforcement and scoping.
- **`test_mechanic_model.py`** / **`test_mechanic_routes.py`** -- creation (manager-only), the salary-visibility rules (own profile vs. anyone's, full roster manager-only), update/delete (manager-only).
- **`test_mechanic_auth.py`** -- mechanic login, password-never-leaked.
- **`test_mechanic_sorting.py`** -- most/open/closed-ticket sorting, `?order=asc`, and that the manager's own zero-ticket row participates correctly in ties.
- **`test_service_ticket_model.py`** / **`test_service_ticket_routes.py`** -- creation (manager-only, requires `cost`), status updates (any mechanic), description/cost edits (manager-only), single-action and bulk mechanic assignment (manager-only, with the bulk route's idempotent-on-redundancy behavior tested explicitly), `my-tickets` scoping.
- **`test_rate_limiting.py`** -- every route-specific limit, the global default, and that a bootstrapped manager/mechanic doesn't itself count toward any limit.
- **`test_mechanic_caching.py`** -- `GET /mechanics` cache and invalidation, now manager-authenticated throughout.
- **`test_error_handlers.py`** -- consistent JSON across every failure mode.

Tests run against a temporary in-memory SQLite database (`TestingConfig`), never the real MySQL database. Since there's no API route to create the first manager account (by design), tests bootstrap one directly via a `seed_manager()`/`create_manager()` helper in `conftest.py`, then log in through the _real_ `/mechanics/login` route -- so even the bootstrapped account is authenticated the normal way, not faked.

### Testing with Postman

Every endpoint was also manually verified against the real running app and real MySQL database. The collection is exported as `Mechanic_Shop_API.postman_collection.json`. For protected routes, log in first (`POST /customers/login` or `POST /mechanics/login`) and use the returned `auth_token` as `Bearer <token>` in the `Authorization` header -- a Scripts/Tests post-response snippet on each login request can auto-save the token into a collection variable so it doesn't need to be copied by hand for every request.

---

## CI

`.github/workflows/ci.yml` runs on every push and pull request to `main`: installs dependencies from `requirements.txt`, runs the full pytest suite, then runs Pylint. `TestingConfig` sets its own fixed `SECRET_KEY`, so CI never needs the real one, and needs no database service or secrets configured at all.

---

## Future Extensions

Ideas deliberately scoped out of this project, to keep the current redesign focused:

- **A third "owner" tier**, distinct from "manager," if a shop with a single owner and multiple managers needed a further-restricted permission (e.g. only the owner can create new managers).
- **Software-vendor-level administration** spanning multiple shops (a true multi-tenant SaaS model, with a `Shop` entity and tenant isolation) -- a substantially larger system than a single-shop API, and out of scope here.
- **Enforced status transitions** (e.g. blocking a jump straight from "Pending" to "Paid") via a real state machine, rather than the current flat, freely-settable `status` field.

---

## Submission Checklist

- [x] Blueprints registered for `customer`, `mechanic`, and `service_ticket`, each with its own `url_prefix`
- [x] Full CRUD implemented for `Customer` and `Mechanic`; `ServiceTicket` create/list/status/edit/assign/remove (no full update/delete on the ticket itself, by design)
- [x] Marshmallow schemas validate and serialize every resource
- [x] Role-based JWT authentication: customer and mechanic login, manager-only vs. any-mechanic route access, ownership checks on customer update/delete
- [x] Rate limiting and caching, reasoned per route
- [x] Pagination on `GET /customers`
- [x] Every error response, including validation failures, shares one consistent `{"error": ...}` envelope
- [x] `seed.py`: Faker-driven demo data with a documented, predictable local password scheme
- [x] Postman collection included in the repo and covers every endpoint, including auth and role-rejection cases
- [x] 120 automated tests passing (`python -m pytest -v`)
- [x] Pylint clean (`python -m pylint app tests config.py`)
- [x] CI workflow passing on GitHub Actions
