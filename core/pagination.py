from fastapi import Query


class Pagination:
    def __init__(
        self,
        page: int = Query(
            default=1,
            ge=1,
            description="Page number, starting from 1.",
        ),
        limit: int = Query(
            default=10,
            ge=1,
            le=100,
            description="Maximum number of records per page.",
        ),
    ):
        self.page = page
        self.limit = limit

    @property
    def offset(self) -> int:
        return (self.page - 1) * self.limit
