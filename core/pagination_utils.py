from sqlalchemy import func, select
from sqlalchemy.orm import Session
from sqlalchemy.sql import Select

from core.pagination import Pagination


def paginate_query(
    db: Session,
    statement: Select,
    pagination: Pagination,
) -> tuple[list, int]:
    count_statement = select(func.count()).select_from(
        statement.order_by(None).subquery()
    )

    total = db.scalar(count_statement) or 0

    paginated_statement = statement.offset(pagination.offset).limit(pagination.limit)

    items = list(db.scalars(paginated_statement).all())

    return items, total
