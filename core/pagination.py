from fastapi import Query


# Groups related pagination parameters into one reusable object.
class Pagination:
    def __init__(
        self,
        skip: int = Query(default=0, ge=0),
        limit: int = Query(default=10, ge=1, le=100),
    ):
        self.skip = skip
        self.limit = limit
