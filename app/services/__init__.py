"""
Service layer: business rules factored out of the route handlers.

Each module here holds the decisions a route needs to make that go
beyond "validate input, read/write the database, return a response" --
duplicate checks, ownership/assignment rules, stock allocation,
account anonymization. Routes call into these functions rather than
embedding the logic inline, so a rule like "a part used on a ticket
can't be deleted" lives in exactly one place, independent of the HTTP
layer, and is testable on its own if that's ever useful.

Nothing here owns the database transaction -- functions mutate
objects and return data or an error, but the calling route still
decides when to db.session.commit().
"""
