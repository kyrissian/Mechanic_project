"""
Shared pagination helper.

Every paginated route in this project (GET /customers,
GET /customers/my-tickets, GET /mechanics, GET /service-tickets/my-tickets)
was independently parsing ?page/?page_size, counting, running the
offset/limit query, and building the same response envelope --
Pylint's duplicate-code check correctly flagged that once several
copies existed. paginate_query() is the single place all of it lives
now: each route builds its own base SQLAlchemy query (with whatever
WHERE clauses it needs) and hands it to this function to execute,
paginate, and serialize.
"""

from flask import request
from sqlalchemy import select

from app.extensions import db


def get_pagination_params(default_page_size, max_page_size):
    """Parse ?page and ?page_size from the current request's query
    string. Invalid or missing values fall back to the given
    defaults rather than erroring -- a malformed query param
    shouldn't break an otherwise valid request. page_size is clamped
    to [1, max_page_size] regardless of what was requested.
    """
    try:
        page = int(request.args.get("page", 1))
    except ValueError:
        page = 1
    page = max(page, 1)

    try:
        page_size = int(request.args.get("page_size", default_page_size))
    except ValueError:
        page_size = default_page_size
    page_size = max(1, min(page_size, max_page_size))

    return page, page_size


def paginate_query(query, order_by, schema, items_key, size_limits):
    """Run a paginated version of `query`, ordered by `order_by`, and
    return the full response envelope: {<items_key>: [...], total,
    page, page_size, total_pages}.

    size_limits is a (default_page_size, max_page_size) pair rather
    than two separate parameters, keeping this function's argument
    count reasonable -- items_key varies by resource ("customers",
    "mechanics", "tickets"), since each route names its list field
    after what it actually contains.
    """
    default_page_size, max_page_size = size_limits
    page, page_size = get_pagination_params(default_page_size, max_page_size)

    total = db.session.execute(
        select(db.func.count()).select_from(query.subquery())
    ).scalar()

    paginated_query = query.order_by(order_by).offset((page - 1) * page_size).limit(page_size)
    items = db.session.execute(paginated_query).scalars().all()

    return {
        items_key: schema.dump(items),
        "total": total,
        "page": page,
        "page_size": page_size,
        "total_pages": (total + page_size - 1) // page_size if total else 0,
    }
