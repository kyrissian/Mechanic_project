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

A Flask + SQLAlchemy + MySQL backend for a mechanic shop, with role-based JWT authentication (customer, mechanic, manager), a real service-ticket lifecycle (status, cost, and parts), a stock-aware inventory system, and a Faker-driven seed script — built on the Application Factory pattern. Built for the "Database Design and Planning with ERDs," "SQLAlchemy Relationships," "Marshmallow Schemas & CRUD Endpoints," "Application Factory Pattern," "Rate Limiting and Caching," "Token Authentication," "Advanced SQLAlchemy Queries," and "Implementing Junction Tables with Additional Fields" course modules.

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
- [Inventory & Stock Tracking](#inventory--stock-tracking)
- [Error Handling](#error-handling)
- [Project Structure](#project-structure)
- [Architecture Notes](#architecture-notes)
- [Testing](#testing)
- [CI](#ci)
- [Future Extensions](#future-extensions)

---

## Changelog

### 2026-09-29: Code Review Pass -- Cache Key Correction and a Database-Level Uniqueness Constraint

A code review (using GitHub Copilot's review feature) surfaced one real, previously-unnoticed bug and one worthwhile hardening suggestion. See [Future Extensions](#future-extensions) for the rest of the review's out-of-scope-for-now suggestions, recorded there rather than acted on.

- **Fixed a real caching bug: `GET /mechanics?page=1` and `?page=2` were sharing one cache entry.** `@cache.cached(timeout=60, key_prefix=MECHANICS_CACHE_KEY)` used a fixed string as its cache key, which does **not** automatically vary by query string -- Flask-Caching requires `query_string=True` for that. This README previously stated (incorrectly) that "each page/page_size combination is cached under its own key"; that was never true until this fix. Whichever page was requested first was the page every subsequent request saw, regardless of what `?page=` actually asked for, until the cache expired or was cleared. Fixed by switching to `@cache.cached(timeout=60, query_string=True)`.
- **Added a composite primary key to the `service_mechanics` junction table** (`ticket_id` + `mechanic_id`). Duplicate-assignment protection previously lived only at the application level (`assign_mechanic` checking `if mechanic in ticket.mechanics` before appending) -- which has a real, if narrow, race-condition gap: two near-simultaneous requests could both pass that check before either commits. The composite primary key makes the database itself refuse a second row for the same pair, regardless of what the application layer does or doesn't catch. This is consistent with the ERD-fidelity correction already made elsewhere in this project (see [Architecture Notes](#architecture-notes)): the lesson's own example doesn't mark either junction-table column as a primary key, but nothing in the assignment actually requires matching that.
- 2 new tests: one confirming pages are now cached separately, one confirming the database rejects a duplicate junction row even when the ORM's own duplicate check is bypassed entirely.

### 2026-09-28: Inventory Resource, Stock Tracking, and Consistent Pagination

- Added a new `Inventory` resource (`/inventory`): parts catalog with `name`, `price`, and `quantity_on_hand`. Full CRUD, manager-only for writes, readable by any logged-in mechanic. A part that has been used on any ticket cannot be deleted (`409`) -- same "history stays" reasoning as ticket records.
- Added `PUT /service-tickets/<id>/add-part/<inventory_id>` (bulk-add-a-part). Open to a manager or a mechanic assigned to that specific ticket. Copies the part's current price onto the ticket line (`unit_price`) so a later price change never rewrites a past ticket's cost, and **decrements `Inventory.quantity_on_hand`** by whatever is actually allocated -- refusing the request with a `400` (naming how many are actually available) if it would over-allocate past what's in stock.
- The junction between `ServiceTicket` and `Inventory` is a full model (`TicketPart`), not a bare `db.Table` -- this is the optional challenge from the "Junction Tables with Additional Fields" lesson, since a ticket needs to record _how many_ of a part it used and at _what price_, not just that a link exists.
- **`PUT /service-tickets/<id>/status` now requires the calling mechanic to actually be assigned to that ticket** (a manager may still update any ticket's status). Previously any logged-in mechanic could change the status of a ticket they had no connection to -- closing that gap.
- **Consistent pagination added to every remaining list route**: `GET /mechanics`, `GET /service-tickets`, `GET /service-tickets/my-tickets`, and `GET /inventory` (joining `GET /customers` and `GET /customers/my-tickets`, already paginated). All four share one `paginate_query()` helper (`app/utils/pagination.py`) rather than four near-duplicate implementations of the same offset/limit/count logic.
- `GET /mechanics`'s cache invalidation switched from deleting one key to `cache.clear()`: since each `page`/`page_size` combination is now cached under its own key, a single-key delete could leave a stale page 2 behind after a write. This is safe specifically because `GET /mechanics` is the only cached route in the app.
- `seed.py` updated: a real parts catalog with realistic per-part stock levels (one part, Brake Rotor, deliberately seeded low so the over-allocation check has a ready-made example to demo), and seeded tickets now attach parts (decrementing stock accordingly) alongside mechanics.
- ~20 new/updated tests covering inventory CRUD, add-part (including stock decrement and over-allocation), status-update ownership, and pagination on every newly-paginated route.

### 2026-09-25: Role-Based Authorization, Ticket Lifecycle, Sorting, and Pagination

This was the largest single change to the project -- a deliberate redesign that goes well beyond the lesson's minimum requirements, aimed at making the API reflect how a real shop would actually operate rather than leaving every action open to everyone.

- **Mechanic authentication and roles.** `Mechanic` gained `password_hash` and `role` (`"mechanic"` or `"manager"`). `POST /mechanics/login` mirrors customer login. Unlike `Customer`, a mechanic account cannot self-register -- only an existing manager can create one.
- **Service ticket lifecycle.** `ServiceTicket` gained `status` (`Pending` → `In Progress` → `Completed` → `Paid` → `Picked Up`) and `cost` (the estimate given up front, editable later). Editing a ticket's description or cost, and assigning or removing mechanics (single or bulk), are manager-only.
- **`service_date` is now a real `Date` column** (was `VARCHAR`), and **`salary`/`cost` use `Decimal`, not float** -- see [Architecture Notes](#architecture-notes) for the story behind this, including a correction to an earlier, mistaken claim in this README about ERD type fidelity being a grading requirement.
- **Bulk mechanic assignment.** `PUT /service-tickets/<id>/edit` takes `add_ids`/`remove_ids` and applies both in one request, idempotently (a redundant add/remove is silently skipped; a nonexistent mechanic id is still a real `404`).
- **Salary privacy.** A regular mechanic can view their own full profile (including salary) but not anyone else's, and cannot see the full roster at all (`GET /mechanics` is manager-only, since it includes everyone's pay). The three sorting/insight endpoints are open to any mechanic but never include salary in their response.
- **Sorting/insight endpoints**, all mechanic-authenticated, all supporting `?order=asc` to reverse the default descending sort: `GET /mechanics/most-tickets`, `GET /mechanics/open-tickets`, `GET /mechanics/closed-tickets`.
- **Customer account deletion became a soft delete with anonymization** (`deleted_at`, scrubbed name/email/phone) rather than a hard delete -- and, after further thought, **a customer with ANY service history cannot delete their account online at all** (`409`): tickets are the shop's business records, and letting a customer scrub the identity attached to them would defeat that purpose. Only a customer with zero tickets can close their own account. A closed account's token stops working immediately (not just at its natural 1-hour expiry), and its email frees up for reuse.
- **Tokens no longer trust their own claims for authorization.** Both `token_required` and `mechanic_token_required` look up the account fresh from the database on every request; a mechanic's `role` is read from that fresh lookup, never from the token payload. This means deleting a mechanic invalidates their token immediately, and promoting/demoting a mechanic takes effect on their very next request -- not their next login.
- **`GET /customers` and `GET /customers/<id>` now require a mechanic token** (any role) -- previously public, which was inconsistent once the rest of the API required authentication and once these responses could include personal data.
- 68 new/updated tests across mechanic auth, mechanic routes, mechanic sorting, service ticket routes, customer routes, rate limiting, and caching.

### 2026-09-23: Token Authentication and Standardized Error Handling

- Added JWT-based token authentication for the `Customer` resource. `POST /customers/login` exchanges an email and password for a token; `GET /customers/my-tickets`, `PUT /customers/<id>`, and `DELETE /customers/<id>` all require a valid token, and the latter two additionally verify the token's customer matches the id in the URL.
- `Customer` gained a `password_hash` column, hashed with `werkzeug.security` and never returned in any response. Not part of the class-provided ERD -- a deliberate, necessary extension for this lesson.
- Standardized every validation-failure response across all three resources to the same `{"error": "...", "details": {...}}` envelope every other error in this API already used -- directly addressing instructor feedback asking for more comprehensive, consistent error handling.
- Added `app/utils/util.py` (`encode_token`, `token_required`) and `app/utils/errors.py` (`validation_error_response`), both shared across blueprints.
- 15 new/updated tests.

### 2026-09-22: Extended Rate Limiting and Caching Coverage

- Rate limited `DELETE /customers/<id>` and `DELETE /mechanics/<id>` to 10 requests per hour per client IP.
- Added a global default limit (`200 per day, 50 per hour`) on the `Limiter` instance itself, applying automatically to every route with no route-specific limit.
- Extended caching to `GET /mechanics/<id>` (later removed once that route also required authentication -- see [Architecture Notes](#architecture-notes)).
- 8 new tests.

### 2026-09-21: Rate Limiting and Caching

- Added Flask-Limiter, rate limiting `POST /customers` to 5 requests per hour per client IP.
- Added Flask-Caching, caching `GET /mechanics` for 60 seconds, with explicit invalidation on every write.
- Config split by environment: `DevelopmentConfig` uses `SimpleCache` and a `memory://` rate-limit store; `TestingConfig` uses `NullCache` and disables rate limiting entirely.
- 10 new tests.

### 2026-09-16: Global Error Handling, CI, and Dependency Fix

- Added global error handlers (`app/error_handlers.py`) so unmatched routes, wrong HTTP methods, and malformed/missing JSON bodies all return consistent JSON.
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

- **1 manager** -- credentials from `.env`.
- **4 core mechanics** -- deliberately uneven ticket loads (one busy, one moderate, one light, one with zero tickets, as if freshly hired).
- **6 extra mechanics** -- never assigned to any ticket, safe to `DELETE` via the API.
- **12 core customers**, each with at least one ticket (and therefore, per the delete policy, cannot be deleted -- only updated).
- **6 extra customers** with no tickets -- safe to `DELETE`.
- **10 core inventory parts**, with realistic names, prices, and starting stock. `Brake Rotor` is deliberately seeded with only 3 in stock, so the over-allocation check on `add-part` has a ready-made example to demo without any manual setup.
- **6 extra inventory parts** -- never attached to any ticket, safe to `DELETE`.
- **33 service tickets**, spread across all five statuses, most with one or more parts attached (which decrements the relevant part's stock during seeding), and VINs generated to satisfy the same ISO-3779-style validator the API itself enforces.

**Password scheme (local demo data only, never for production):** every seeded customer's password is `customerpassword<id>`, and every seeded regular mechanic's password is `mechanicpassword<id>`, where `<id>` is that record's real database id. The manager account is the one exception, using whatever you set in `.env`.

**Emails are name-matched, not random.** Rather than Faker's independent `fake.email()` (which has no relationship to the name on the same row), each record's email is built directly from its generated name (e.g. `erin.wallace@example.com`), so it's recognizable at a glance in MySQL Workbench. Phone numbers use a fixed `555-###-####` pattern rather than Faker's default, which sometimes appends an extension or uses inconsistent international formatting.

Running `seed.py` again wipes and rebuilds from scratch -- it does not merge with or preserve anything added since the last run, including data created by hand through Postman, or a password changed via `PUT /customers/<id>`/`PUT /mechanics/<id>`. This is intentional: the predictable password scheme only holds if ids are predictable, which requires starting from an empty database every time.

---

## Entity-Relationship Diagram

Models started from the class-provided ERD, with several deliberate departures made once it was confirmed that nothing in the assignment actually requires exact type fidelity to it (see [Architecture Notes](#architecture-notes)):

- **Customer** -- `id`, `name`, `email`, `phone`, plus `password_hash` and `deleted_at` (not in the original ERD -- added for login and soft-delete)
- **Mechanic** -- `id`, `name`, `email`, `phone`, `salary` (`Decimal`, was `FLOAT`), plus `password_hash` and `role` (not in the original ERD)
- **Service_Ticket** -- `id`, `vin`, `service_date` (real `Date`, was `VARCHAR`), `service_desc`, plus a foreign key to `Customer`, plus `status` and `cost` (not in the original ERD)
- **Inventory** -- `id`, `name`, `price` (`Decimal`), `quantity_on_hand` -- not in the original ERD at all; added for this lesson's new resource
- **Service_Mechanics** (junction table, `db.Table`) -- `ticket_id` + `mechanic_id`, linking `Service_Ticket` and `Mechanic`
- **Ticket_Part** (junction **model**, not a bare table) -- `ticket_id` + `inventory_id` (composite primary key), `quantity`, `unit_price`. Modeled as a full class, per the optional challenge in the "Junction Tables with Additional Fields" lesson, specifically because a ticket needs to record how many of a part it used and at what price -- data a bare `db.Table` junction can't hold.

Relationships:

- **Customer → Service_Ticket**: one-to-many
- **Service_Ticket ↔ Mechanic**: many-to-many, via `Service_Mechanics`
- **Service_Ticket ↔ Inventory**: many-to-many, via `Ticket_Part`

---

## Roles & Authorization

Two roles exist on `Mechanic`: `"mechanic"` and `"manager"`. There is no third tier, and no concept of a software-vendor-level "admin" spanning multiple shops -- see [Future Extensions](#future-extensions).

Every route's access level was reasoned through individually, the same way rate limiting and caching were:

| Action                                                                 | Who                                                           | Why                                                                                                                                                     |
| ---------------------------------------------------------------------- | ------------------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------- |
| Create a mechanic account                                              | Manager only                                                  | Staff accounts cannot self-register; letting any mechanic create (or promote) another would defeat the purpose of having roles.                         |
| View the full mechanic roster (with salary)                            | Manager only                                                  | Salary is sensitive; a regular mechanic has no legitimate reason to see everyone's pay.                                                                 |
| View a single mechanic's profile (with salary)                         | The mechanic themselves, or a manager                         | A mechanic can always see their own salary; only a manager can look up someone else's.                                                                  |
| Update or delete a mechanic account                                    | Manager only                                                  | Roster changes -- including salary and role -- are a management decision.                                                                               |
| Create a service ticket                                                | Manager only                                                  | Creation sets `cost` and `service_desc` up front, both otherwise manager-controlled.                                                                    |
| View tickets (list, single, or "my tickets")                           | Any logged-in mechanic                                        | Staff need visibility into the queue; "my tickets" is scoped to what that mechanic is personally assigned to.                                           |
| Edit a ticket's description/cost                                       | Manager only                                                  | Same reasoning as ticket creation.                                                                                                                      |
| Update a ticket's status                                               | A manager, or a mechanic **assigned to that specific ticket** | This is work a mechanic performs, but only on jobs they actually have -- a mechanic with no connection to a ticket has no business changing its status. |
| Assign/remove mechanics (single or bulk)                               | Manager only                                                  | Assigning staff to work is a management decision.                                                                                                       |
| Add a part to a ticket                                                 | A manager, or a mechanic **assigned to that specific ticket** | Same reasoning as status updates -- only someone actually working the job should say what it used.                                                      |
| Sorting/insight endpoints (most-tickets, open-tickets, closed-tickets) | Any logged-in mechanic                                        | Useful to everyone for gauging workload; response never includes salary.                                                                                |
| Inventory reads                                                        | Any logged-in mechanic                                        | Staff need part names, prices, and stock to do their work.                                                                                              |
| Inventory create/update/delete                                         | Manager only                                                  | Prices and stock levels are a management decision.                                                                                                      |

A customer's own authorization is unchanged: they can view their own tickets (`GET /customers/my-tickets`, read-only, status visible but not editable) and manage their own account, and nothing else. `GET /customers` and `GET /customers/<id>` require a mechanic token (any role) -- customer records contain personal data, so browsing them is staff-only, not public.

---

## API Endpoints

All request/response bodies are JSON. Routes marked 🔒 require a valid Bearer token (customer or mechanic, as noted); 👔 marks manager-only routes; 🔧 marks routes open to a manager **or** a mechanic assigned to that specific ticket. List routes marked 📄 are paginated -- see [Pagination](#pagination).

### Customer (`/customers`)

| Method    | URL                     | Purpose                                                                        |
| --------- | ----------------------- | ------------------------------------------------------------------------------ |
| POST      | `/customers`            | Create (register) a customer                                                   |
| POST      | `/customers/login`      | Log in, receive a JWT                                                          |
| GET 🔒 📄 | `/customers`            | List customers                                                                 |
| GET 🔒    | `/customers/<id>`       | Get one customer                                                               |
| GET 🔒 📄 | `/customers/my-tickets` | The logged-in customer's own tickets                                           |
| PUT 🔒    | `/customers/<id>`       | Update a customer (own account only)                                           |
| DELETE 🔒 | `/customers/<id>`       | Close a customer's account (own account, no service history only -- see below) |

### Mechanic (`/mechanics`)

| Method    | URL                         | Purpose                                              |
| --------- | --------------------------- | ---------------------------------------------------- |
| POST 👔   | `/mechanics`                | Create a mechanic                                    |
| POST      | `/mechanics/login`          | Log in, receive a JWT (carries the mechanic's role)  |
| GET 👔 📄 | `/mechanics`                | List all mechanics, including salary                 |
| GET 🔒    | `/mechanics/<id>`           | Get one mechanic -- own profile, or any if manager   |
| GET 🔒    | `/mechanics/most-tickets`   | Mechanics sorted by total tickets worked (`?order=`) |
| GET 🔒    | `/mechanics/open-tickets`   | Mechanics sorted by open ticket count (`?order=`)    |
| GET 🔒    | `/mechanics/closed-tickets` | Mechanics sorted by closed ticket count (`?order=`)  |
| PUT 👔    | `/mechanics/<id>`           | Update a mechanic                                    |
| DELETE 👔 | `/mechanics/<id>`           | Delete a mechanic                                    |

### Service Ticket (`/service-tickets`)

| Method    | URL                                                   | Purpose                                                 |
| --------- | ----------------------------------------------------- | ------------------------------------------------------- |
| POST 👔   | `/service-tickets`                                    | Create a service ticket                                 |
| GET 🔒 📄 | `/service-tickets`                                    | List all service tickets                                |
| GET 🔒 📄 | `/service-tickets/my-tickets`                         | Tickets the logged-in mechanic is assigned to           |
| GET 🔒    | `/service-tickets/<id>`                               | Get one service ticket                                  |
| PUT 👔    | `/service-tickets/<id>`                               | Update description and/or cost                          |
| PUT 🔧    | `/service-tickets/<id>/status`                        | Update status                                           |
| PUT 👔    | `/service-tickets/<id>/assign-mechanic/<mechanic_id>` | Assign one mechanic to a ticket                         |
| PUT 👔    | `/service-tickets/<id>/remove-mechanic/<mechanic_id>` | Remove one mechanic from a ticket                       |
| PUT 👔    | `/service-tickets/<id>/edit`                          | Bulk add/remove mechanics (`add_ids`/`remove_ids`)      |
| PUT 🔧    | `/service-tickets/<id>/add-part/<inventory_id>`       | Add a part to the ticket (`{"quantity": n}`, default 1) |

### Inventory (`/inventory`)

| Method    | URL               | Purpose                                                            |
| --------- | ----------------- | ------------------------------------------------------------------ |
| POST 👔   | `/inventory`      | Create a part                                                      |
| GET 🔒 📄 | `/inventory`      | List all parts                                                     |
| GET 🔒    | `/inventory/<id>` | Get one part                                                       |
| PUT 👔    | `/inventory/<id>` | Update a part's name/price/stock                                   |
| DELETE 👔 | `/inventory/<id>` | Delete a part (blocked with `409` if it's been used on any ticket) |

Deliberately no full `PUT`/`DELETE` for the ticket resource itself -- only the scoped detail/status/mechanic/part routes above -- so a completed or in-progress service record is never silently overwritten or erased wholesale.

---

## Authentication

Two independent JWT flows exist, both signed with the same `SECRET_KEY` but distinguished by a `"type"` claim in the token payload (`"customer"` or `"mechanic"`) -- without that claim, a customer's own valid token could potentially be presented to a mechanic-only route (or vice versa) if their ids happened to collide.

### Customer flow

1. `POST /customers` registers an account with a hashed password.
2. `POST /customers/login` exchanges email/password for a token (`encode_token`).
3. `token_required` re-reads the account from the database on every request (not just the token's claims) and passes the customer's own id into the route -- a closed account's token stops working immediately, rather than remaining valid until its natural 1-hour expiry.

### Mechanic flow

1. `POST /mechanics` (manager-only) creates a mechanic account with a role and a hashed password.
2. `POST /mechanics/login` exchanges email/password for a token that also carries the mechanic's role (`encode_mechanic_token`).
3. `mechanic_token_required` re-reads the mechanic from the database on every request and passes the mechanic's id and their **current** role (read fresh, never from the token's own `role` claim) into the route. A deleted mechanic's token is rejected immediately; a promoted or demoted mechanic's access changes on their very next request, not their next login.
4. `manager_required` wraps `mechanic_token_required`, additionally checking that the (freshly looked-up) role is `"manager"`.

Both logins return the identical `401` message for a wrong password and an unregistered email, so a client can never use the response to enumerate which accounts exist.

A limited, cached, or authenticated response carries the same status codes and JSON shape described in [Error Handling](#error-handling), with these additions:

- A missing, malformed, expired, or wrong-type token returns `401` with `{"error": "..."}`.
- A structurally valid token whose account no longer exists, is inactive, has the wrong role, or belongs to the wrong owner returns `401` or `403` with `{"error": "..."}`, as appropriate.

---

## Rate Limiting & Caching

Every route decision comes down to one question: **how often is this route abused or destructive (for limiting), and how often is its data read versus written (for caching)?**

### Rate limiting

| Route                                                                          | Limit                                      | Why                                                                                                                                                              |
| ------------------------------------------------------------------------------ | ------------------------------------------ | ---------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `POST /customers`                                                              | 5 / hour / IP                              | Creation is the write path most open to abuse. Rejected (400) attempts still count toward the limit, which is what stops probing for registered emails.          |
| `POST /mechanics`                                                              | 5 / hour / IP                              | Same reasoning, though it never touches legitimate use -- a real shop only registers a handful of mechanics total, and only a manager can even reach this route. |
| `POST /customers/login` / `POST /mechanics/login`                              | 10 / hour / IP                             | Login is a classic brute-force target. Both failed and successful attempts count toward the limit.                                                               |
| `DELETE /customers/<id>` / `DELETE /mechanics/<id>` / `DELETE /inventory/<id>` | 10 / hour / IP                             | Deletion is the most destructive route on each resource.                                                                                                         |
| Every other route                                                              | 200 / day, 50 / hour / IP (global default) | A floor applied via `default_limits` on the `Limiter` instance itself, catching every route with no limit of its own.                                            |

### Caching

| Route                                                                                 | Cached?         | Why                                                                                                                                                                                                                                                                                                                                                                                                      |
| ------------------------------------------------------------------------------------- | --------------- | -------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `GET /mechanics`                                                                      | Yes, 60s        | The roster is read constantly but written to rarely. **The one cached route in the app right now.** `@cache.cached(..., query_string=True)` so each `page`/`page_size` combination gets its own cache entry (see the 2026-09-29 changelog entry for a bug this fixed); writes call `cache.clear()` rather than deleting a single key, since a targeted delete could otherwise leave a stale page behind. |
| `GET /mechanics/<id>`                                                                 | **No, removed** | Once this route required authentication, `@cache.memoize` would key each cache entry by the _requesting_ mechanic's id too -- every different requester caching their own separate copy, which `cache.delete_memoized()` could no longer reliably clear. No longer worth the complexity for now-authenticated, internal traffic.                                                                         |
| `GET /customers`, `GET /service-tickets`, `GET /inventory`, and the sorting endpoints | No              | Written to too often (customers/tickets/inventory all change constantly; the sorting endpoints depend on shop-wide ticket-assignment activity) for a timed cache to stay accurate.                                                                                                                                                                                                                       |

Authentication is always the _outer_ decorator on a cached route (`@manager_required` above `@cache.cached`), never the reverse: Flask-Caching keys its cache by the request path, not by who's asking, so if caching ran first, one authenticated request's response could be served to a later, completely unauthenticated one hitting the same path.

---

## Pagination

Every list route in the API is paginated through one shared helper, `paginate_query()` (`app/utils/pagination.py`):

```
GET /customers?page=2&page_size=10
```

- `page` defaults to `1`; invalid or missing values fall back to the default rather than erroring.
- `page_size` has a route-specific default and cap (see table below), so a client can't pull an unbounded number of rows in one call.
- A `page` past the last real page returns an **empty list**, not a `404` -- the request itself is valid, there's just nothing there.
- Results are always ordered by `id`, so pages never overlap or skip rows.

| Route                             | Default page size | Max page size | Why this default                                                                                                  |
| --------------------------------- | ----------------- | ------------- | ----------------------------------------------------------------------------------------------------------------- |
| `GET /customers`                  | 7                 | 50            | A manageable browse size for staff.                                                                               |
| `GET /customers/my-tickets`       | 2                 | 20            | Each ticket carries status, cost, mechanics, and a parts list -- heavier than it looks even a couple at a time.   |
| `GET /mechanics`                  | 5                 | 25            | A shop's roster is typically small; this is a comfortable browse size.                                            |
| `GET /service-tickets`            | 3                 | 30            | Same "each ticket is heavy" reasoning as the customer ticket list, sized slightly larger for a staff browse view. |
| `GET /service-tickets/my-tickets` | 2                 | 20            | Mirrors the customer version.                                                                                     |
| `GET /inventory`                  | 5                 | 25            | A comfortable browse size for a parts catalog.                                                                    |

Response shape (the list key name varies by resource -- `customers`, `mechanics`, `tickets`, or `inventory`):

```json
{
    "customers": [ ... ],
    "total": 14,
    "page": 1,
    "page_size": 7,
    "total_pages": 2
}
```

---

## Inventory & Stock Tracking

`Inventory` tracks the shop's parts catalog: `name`, `price`, and `quantity_on_hand`. It relates to `ServiceTicket` many-to-many through `TicketPart`, a full model (not a bare `db.Table`) that additionally records `quantity` (how many of that part were used on that specific ticket) and `unit_price` (the part's price at the moment it was added).

**Why `unit_price` is copied onto each line rather than looked up live:** if a part's catalog price changes later, every past ticket that used it would otherwise silently show a different total cost than what the customer actually agreed to. Snapshotting the price at add-time keeps historical tickets accurate regardless of later repricing.

**Stock is decremented automatically, and over-allocation is refused.** `PUT /service-tickets/<id>/add-part/<inventory_id>` checks `quantity_on_hand` before allocating: requesting more of a part than the shop has in stock returns `400` naming exactly how many are available, and nothing changes. A successful add reduces `quantity_on_hand` by the amount allocated -- so stock levels stay accurate as a side effect of normal use, rather than depending on a manager remembering to update them by hand after every job. `quantity_on_hand` can still be edited directly via `PUT /inventory/<id>` (e.g. after receiving a new shipment).

**A part used on any ticket cannot be deleted** (`409`) -- the same "history stays" principle applied to customer accounts with service history and to tickets themselves.

---

## Error Handling

Every error response in this API shares the same `{"error": "..."}` envelope, no matter which layer produces it.

- **HTTP-level errors** (404, 405, 400 malformed JSON, 415, etc.) are caught by a global handler and returned as `{"error": "..."}`.
- **Unexpected exceptions** are caught, logged server-side, and returned as a generic `{"error": "An unexpected server error occurred."}` with a 500.
- **Rate limit violations** return `429` with `{"error": "Rate limit exceeded", "detail": "..."}`.
- **Validation failures** return `400` with `{"error": "Validation failed.", "details": {...}}`, where `details` is Marshmallow's own field-by-field message dict -- built by a single shared helper, `validation_error_response()`, called from every blueprint.
- **Authentication/authorization failures** return `401` (missing/invalid/expired/wrong-type token, or an account that no longer exists/is inactive) or `403` (valid token, wrong owner or wrong role/assignment).
- **Business-rule conflicts** return `409` (deleting a customer with service history, deleting a mechanic-used part) -- the request is well-formed, but conflicts with data the system must preserve.
- **Expected application-level failures** with their own specific messages (`"Customer not found."`, `"Email already associated with an account."`, `"Not enough Brake Rotor in stock. Requested 4, only 3 available."`, etc.) are returned directly by each route.

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
      pagination.py              # paginate_query() -- shared pagination, used by
                                 # every list route across all four blueprints
    models/
      __init__.py
      customer.py                # includes password_hash, deleted_at
      mechanic.py                 # includes password_hash, role; salary is Decimal
      service_ticket.py           # includes status, cost; service_date is Date
      service_mechanics.py        # bare db.Table junction (Mechanic <-> ServiceTicket)
      inventory.py                 # name, price, quantity_on_hand
      ticket_part.py               # MODELED junction (ServiceTicket <-> Inventory):
                                    # quantity, unit_price
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
        routes.py                 # CRUD + status/edit/bulk-edit/add-part, role-gated
        schemas.py                # ServiceTicketSchema + supporting schemas,
                                   # VALID_STATUSES/OPEN_STATUSES/CLOSED_STATUSES
      inventory/
        __init__.py
        routes.py                 # CRUD, manager-gated writes
        schemas.py                # InventorySchema
  tests/
    __init__.py
    conftest.py                 # fixtures, payload helpers, manager/mechanic bootstrap
    test_customer_model.py
    test_mechanic_model.py
    test_service_ticket_model.py
    test_inventory_model.py
    test_customer_routes.py     # includes pagination tests
    test_mechanic_routes.py
    test_mechanic_auth.py
    test_mechanic_sorting.py
    test_mechanic_caching.py
    test_service_ticket_routes.py
    test_ticket_parts.py         # add-part: stock decrement, over-allocation
    test_inventory_routes.py
    test_customer_auth.py
    test_customer_deletion.py
    test_rate_limiting.py
    test_error_handlers.py
```

---

## Architecture Notes

### On the ERD-fidelity principle -- a correction

An earlier version of this README justified matching the class-provided ERD's exact column types (`service_date` as `VARCHAR`, `salary` as `FLOAT`) by claiming these models were "graded against this specific diagram." On review of the actual assignment instructions, **that was never true** -- the assignment specifies required fields, routes, and schemas, but says nothing about strict type fidelity to the diagram. That framing was a design principle introduced along the way, not an instructor requirement, and this README previously stated it inaccurately. Having confirmed that, `service_date` was changed to a real `Date` column and `salary`/`cost` to `Decimal`, both textbook-correct choices this project can now make freely.

### Why not a single `app.py`, like the lesson shows?

Wrapping app creation in `create_app()` (the Application Factory pattern) means each test can get a fresh, fully isolated app backed by an in-memory database, without ever touching real data -- a single module-level `app = Flask(__name__)` gets created once, permanently wired to the real database, the moment the file is imported.

### Blueprints, one folder per resource

Each resource's routes and schema live together in their own folder under `app/blueprints/`. Each blueprint's `__init__.py` creates the `Blueprint` object, then imports its own `routes.py` at the very bottom, avoiding a circular import.

### Provider-style separation

- `app/extensions.py` holds `db`, `ma`, `limiter`, and `cache`, kept separate from `app/__init__.py` to avoid a circular import between model/schema files and the app factory.
- `app/utils/util.py` holds both token flows and all three access-control decorators, so every blueprint imports from one place rather than duplicating auth logic.
- **`manager_required`'s inner wrapper parameter is named `requester_id`, not `mechanic_id`** -- several routes it decorates (`update_mechanic`, `delete_mechanic`, `assign_mechanic`, `remove_mechanic`) have a URL parameter _also_ named `mechanic_id`. Flask passes URL parameters as keyword arguments, so if the wrapper's own parameter shared that name, Python would raise "got multiple values for argument" the moment both tried to bind to the same name -- a real bug caught while writing this feature's tests, not merely a style choice.
- **`app/utils/pagination.py`'s `paginate_query()`** exists because four different list routes were each independently parsing `?page`/`?page_size`, counting, running the offset/limit query, and building the same response envelope -- Pylint's duplicate-code check correctly flagged that once several copies existed. Every route now just builds its own base SQLAlchemy query (with whatever `WHERE` clauses it needs) and hands it to this one function.
- `cache = Cache()` in `extensions.py` is created with no config, so `TestingConfig` can override the backend (`SimpleCache` vs `NullCache`) through `app.config` rather than the constructor overriding it.
- `limiter = Limiter(..., default_limits=[...])` sets its global floor on the constructor, matching this project's `init_app()`-based wiring elsewhere.
- `ServiceTicketSchema`, `MechanicSchema`, and `InventorySchema` all declare money fields as `fields.Decimal(as_string=True, places=2, ...)` -- serializing a fixed-precision string (`"450.00"`) so every money value in the API formats identically, while still accepting an int/float/string on input.
- `VALID_ROLES`, `VALID_STATUSES`, `OPEN_STATUSES`, and `CLOSED_STATUSES` are each defined once, in their owning schema module, and imported wherever else they're needed -- so the set of valid values and the routes that depend on it can never drift out of sync.
- `TicketPart`'s primary key is the `(ticket_id, inventory_id)` pair (not its own `id` column), so a part can only ever have one line per ticket -- adding the same part again increases that line's `quantity` instead of creating a duplicate row.

---

## Testing

### Automated tests

Run the full suite:

```powershell
python -m pytest -v
```

Currently: **173 tests, all passing.**

- **`test_customer_model.py`** / **`test_customer_routes.py`** -- creation, uniqueness, auth/ownership on update/delete, pagination.
- **`test_customer_auth.py`** -- login, password-never-leaked, `my-tickets` token enforcement and scoping.
- **`test_customer_deletion.py`** -- soft-delete anonymization; the no-service-history-only delete policy; token invalidation on closure; email reuse after closure.
- **`test_mechanic_model.py`** / **`test_mechanic_routes.py`** -- creation (manager-only), salary-visibility rules, pagination on the roster.
- **`test_mechanic_auth.py`** -- mechanic login, deleted-mechanic token invalidation, role changes taking effect without re-login.
- **`test_mechanic_sorting.py`** -- most/open/closed-ticket sorting, `?order=asc`.
- **`test_mechanic_caching.py`** -- `GET /mechanics` cache and invalidation, including that a write invalidates every cached page, not just page 1.
- **`test_service_ticket_model.py`** / **`test_service_ticket_routes.py`** -- creation, status updates (now ownership-gated), description/cost edits, single-action and bulk mechanic assignment, pagination.
- **`test_inventory_model.py`** / **`test_inventory_routes.py`** -- creation, uniqueness, role-gated CRUD, the used-part delete block.
- **`test_ticket_parts.py`** -- `add-part`: stock decrement, quantity-bump on repeat add, over-allocation rejection, price-snapshot immutability, assignment-based authorization.
- **`test_rate_limiting.py`** -- every route-specific limit, the global default, and that a bootstrapped manager/mechanic doesn't itself count toward any limit.
- **`test_error_handlers.py`** -- consistent JSON across every failure mode.

Tests run against a temporary in-memory SQLite database (`TestingConfig`), never the real MySQL database. Since there's no API route to create the first manager account (by design), tests bootstrap one directly via a `seed_manager()`/`create_manager()` helper in `conftest.py`, then log in through the _real_ `/mechanics/login` route.

### Testing with Postman

Every endpoint was also manually verified against the real running app and real MySQL database. The collection is exported as `Mechanic_Shop_API.postman_collection.json`. For protected routes, log in first (`POST /customers/login` or `POST /mechanics/login`) and use the returned `auth_token` as `Bearer <token>` in the `Authorization` header -- each login request's Scripts/Tests tab auto-saves the token into a collection variable (`auth_token`, `manager_token`, or `mechanic_token`) so it doesn't need to be copied by hand.

---

## CI

`.github/workflows/ci.yml` runs on every push and pull request to `main`: installs dependencies from `requirements.txt`, runs the full pytest suite, then runs Pylint. `TestingConfig` sets its own fixed `SECRET_KEY`, so CI never needs the real one, and needs no database service or secrets configured at all.

---

## Future Extensions

Ideas deliberately scoped out of this project, to keep each round of work focused:

- **A third "owner" tier**, distinct from "manager," if a shop with a single owner and multiple managers needed a further-restricted permission.
- **Software-vendor-level administration** spanning multiple shops (a true multi-tenant SaaS model) -- a substantially larger system than a single-shop API.
- **Enforced status transitions** (e.g. blocking a jump straight from "Pending" to "Paid") via a real state machine, rather than the current flat, freely-settable `status` field.
- **A staff-side "anonymize this account" route** for a customer _with_ service history, for a legitimate privacy request or after a retention period -- today, only a customer with zero tickets can close their own account, by design; a manager-initiated path for the with-history case was deliberately left unbuilt.
- **A richer junction between `Mechanic` and `ServiceTicket`**, upgrading `service_mechanics` from a `db.Table` (now with a composite primary key, but still just a link) to a full model, adding `assigned_at`, `role_on_ticket` (e.g. lead vs. assisting), and a separate per-mechanic work log (task description, date, hours) -- so "who did the hardest work" can be judged from real task detail and time spent, not just headcount. `TicketPart` (`Inventory` ↔ `ServiceTicket`) already demonstrates this same modeled-junction pattern for parts; this would apply the same idea to mechanic assignment.

### Ideas for production hardening

A code review pass (GitHub Copilot) suggested several improvements genuinely worth having in a real deployment, but out of scope for this project as a course submission. Recorded here rather than built:

- **Optimistic concurrency on `PUT` routes** (an ETag or `updated_at` check), to prevent one update from silently overwriting another made a moment earlier.
- **Structured audit logging** for sensitive actions -- role changes, deletions, ticket status transitions, inventory mutations -- so there's a record of who changed what and when, beyond what the database itself shows.
- **Enforced ticket status transitions** via a real state machine (e.g. disallowing a jump backward from `Paid` to `In Progress`), already noted above as its own item.
- **Request correlation IDs**, included in error responses and server-side logs, to make a single request traceable end to end.
- **OpenAPI/Swagger documentation**, with contract tests run against the generated spec.
- **Performance testing and indexing** for the sorting/pagination endpoints at real scale (e.g. indexes on `status`, `customer_id`, and the junction tables), since none of this project's endpoints have been load-tested.
- **Redis-backed cache and rate-limit stores**, replacing the current in-memory ones -- necessary for correctness the moment this API runs as more than one process, since in-memory state isn't shared across processes.
- **Property-based testing** for validators (VIN format, pagination parameters, quantity ranges) to stress unusual inputs beyond the specific cases this project's tests cover.
- **Additional security-hardening tests** around token tampering, expired tokens, and mixed token-type misuse, systematically applied across every protected route rather than the representative cases already covered.

---

## Submission Checklist

- [x] Blueprints registered for `customer`, `mechanic`, `service_ticket`, and `inventory`, each with its own `url_prefix`
- [x] Full CRUD implemented for `Customer`, `Mechanic`, and `Inventory`; `ServiceTicket` create/list/status/edit/assign/remove/add-part (no full update/delete on the ticket itself, by design)
- [x] Marshmallow schemas validate and serialize every resource
- [x] Role-based JWT authentication: customer and mechanic login, manager-only vs. any-mechanic vs. assigned-mechanic route access, ownership checks throughout
- [x] Rate limiting and caching, reasoned per route
- [x] Pagination on every list route (`customers`, `mechanics`, `service-tickets`, `my-tickets` x2, `inventory`)
- [x] `TicketPart` is a modeled junction table with `quantity` and `unit_price` (optional challenge)
- [x] Inventory stock (`quantity_on_hand`) decrements automatically on use and blocks over-allocation
- [x] Every error response, including validation failures, shares one consistent `{"error": ...}` envelope
- [x] `seed.py`: Faker-driven demo data with a documented, predictable local password scheme
- [x] Postman collection included in the repo and covers every endpoint, including auth, role-rejection, and business-rule-conflict cases
- [x] 173 automated tests passing (`python -m pytest -v`)
- [x] Pylint clean (`python -m pylint app tests config.py`)
- [x] CI workflow passing on GitHub Actions
