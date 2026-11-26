from api.docs.common import success_example_response
from api.docs.errors import (
    BAD_REQUEST_RESPONSE,
    CONFLICT_RESPONSE,
    FORBIDDEN_RESPONSE,
    NOT_FOUND_RESPONSE,
    UNAUTHORIZED_RESPONSE,
)

COMMENT_EXAMPLE = {
    "id": 201,
    "ticket_id": 101,
    "user_id": 5,
    "author": {
        "id": 5,
        "email": "requester@example.com",
    },
    "message": "The issue still occurs after restarting the laptop.",
    "is_internal": False,
    "created_at": "2026-11-26T06:30:00Z",
}

CATEGORY_EXAMPLE = {
    "id": 7,
    "name": "Wi-Fi Connectivity",
}

DEPARTMENT_EXAMPLE = {
    "id": 2,
    "name": "Network Support",
    "created_at": "2026-11-20T09:00:00Z",
}

USER_EXAMPLE = {
    "id": 5,
    "email": "requester@example.com",
    "department_id": 2,
    "is_active": True,
}

AGENT_EXAMPLE = {
    "id": 3,
    "email": "agent@example.com",
    "department_id": 2,
    "is_active": True,
}

ROLE_ASSIGNMENT_EXAMPLE = {
    "user_id": 5,
    "role_id": 2,
}


def request_example(example):
    return {
        "requestBody": {
            "content": {
                "application/json": {
                    "example": example,
                },
            },
        },
    }


COMMENT_CREATE_RESPONSES = {
    201: success_example_response(
        "Comment created successfully.",
        COMMENT_EXAMPLE,
    ),
}

COMMENT_LIST_RESPONSES = {
    200: success_example_response(
        "Paginated list of accessible ticket comments.",
        {
            "total": 1,
            "page": 1,
            "limit": 10,
            "items": [COMMENT_EXAMPLE],
        },
    ),
}

CATEGORY_LIST_RESPONSES = {
    200: success_example_response(
        "Paginated list of active categories.",
        {
            "total": 1,
            "page": 1,
            "limit": 10,
            "items": [CATEGORY_EXAMPLE],
        },
    ),
}

CATEGORY_CREATE_RESPONSES = {
    201: success_example_response(
        "Category created successfully.",
        CATEGORY_EXAMPLE,
    ),
}

CATEGORY_UPDATE_RESPONSES = {
    200: success_example_response(
        "Category renamed successfully.",
        {
            **CATEGORY_EXAMPLE,
            "name": "Wireless Network Connectivity",
        },
    ),
}

CATEGORY_DELETE_RESPONSES = {
    200: success_example_response(
        "Category deactivated successfully.",
        CATEGORY_EXAMPLE,
    ),
}

DEPARTMENT_LIST_RESPONSES = {
    200: success_example_response(
        "Paginated list of departments.",
        {
            "total": 1,
            "page": 1,
            "limit": 10,
            "items": [DEPARTMENT_EXAMPLE],
        },
    ),
}

DEPARTMENT_DETAIL_RESPONSES = {
    200: success_example_response(
        "Department retrieved successfully.",
        DEPARTMENT_EXAMPLE,
    ),
}

DEPARTMENT_CREATE_RESPONSES = {
    201: success_example_response(
        "Department created successfully.",
        DEPARTMENT_EXAMPLE,
    ),
}

DEPARTMENT_UPDATE_RESPONSES = {
    200: success_example_response(
        "Department renamed successfully.",
        {
            **DEPARTMENT_EXAMPLE,
            "name": "Network Operations",
        },
    ),
}

AGENT_LIST_RESPONSES = {
    200: success_example_response(
        "Paginated list of active agents.",
        {
            "total": 1,
            "page": 1,
            "limit": 10,
            "items": [AGENT_EXAMPLE],
        },
    ),
}

USER_CREATE_RESPONSES = {
    201: success_example_response(
        "User account created successfully.",
        USER_EXAMPLE,
    ),
}

USER_LIST_RESPONSES = {
    200: success_example_response(
        "Paginated list of users.",
        {
            "total": 1,
            "page": 1,
            "limit": 10,
            "items": [USER_EXAMPLE],
        },
    ),
}

USER_DETAIL_RESPONSES = {
    200: success_example_response(
        "User retrieved successfully.",
        USER_EXAMPLE,
    ),
}

USER_STATUS_RESPONSES = {
    200: success_example_response(
        "Account status updated successfully.",
        {
            **USER_EXAMPLE,
            "is_active": False,
        },
    ),
}

PASSWORD_CHANGE_RESPONSES = {
    200: success_example_response(
        "Password changed successfully.",
        {
            "message": "Password changed successfully",
        },
    ),
}

ROLE_ASSIGNMENT_RESPONSES = {
    201: success_example_response(
        "Role assigned successfully.",
        ROLE_ASSIGNMENT_EXAMPLE,
    ),
}

RESOURCE_ERROR_RESPONSES = {
    400: BAD_REQUEST_RESPONSE,
    401: UNAUTHORIZED_RESPONSE,
    403: FORBIDDEN_RESPONSE,
    404: NOT_FOUND_RESPONSE,
    409: CONFLICT_RESPONSE,
}


def add_error_responses(
    responses: dict,
    *status_codes: int,
) -> None:
    responses.update(
        {
            status_code: RESOURCE_ERROR_RESPONSES[status_code]
            for status_code in status_codes
        }
    )


# Comments
add_error_responses(
    COMMENT_CREATE_RESPONSES,
    401,
    403,
    404,
)

add_error_responses(
    COMMENT_LIST_RESPONSES,
    401,
    404,
)
# Categories
add_error_responses(
    CATEGORY_LIST_RESPONSES,
    401,
    403,
)

add_error_responses(
    CATEGORY_CREATE_RESPONSES,
    401,
    403,
    404,
    409,
)

add_error_responses(
    CATEGORY_UPDATE_RESPONSES,
    401,
    403,
    404,
    409,
)

add_error_responses(
    CATEGORY_DELETE_RESPONSES,
    401,
    403,
    404,
    409,
)

# Departments
add_error_responses(
    DEPARTMENT_LIST_RESPONSES,
    401,
    403,
)

add_error_responses(
    DEPARTMENT_DETAIL_RESPONSES,
    401,
    403,
    404,
)

add_error_responses(
    DEPARTMENT_CREATE_RESPONSES,
    401,
    403,
    409,
)

add_error_responses(
    DEPARTMENT_UPDATE_RESPONSES,
    400,
    401,
    403,
    404,
    409,
)

# Agents
add_error_responses(
    AGENT_LIST_RESPONSES,
    401,
    403,
)

DEPARTMENT_AGENT_LIST_RESPONSES = {
    **AGENT_LIST_RESPONSES,
    404: NOT_FOUND_RESPONSE,
}
# Users
add_error_responses(
    USER_CREATE_RESPONSES,
    401,
    403,
    404,
    409,
)

add_error_responses(
    USER_LIST_RESPONSES,
    401,
    403,
)

add_error_responses(
    USER_DETAIL_RESPONSES,
    401,
    403,
    404,
)

add_error_responses(
    USER_STATUS_RESPONSES,
    400,
    401,
    403,
    404,
    409,
)

add_error_responses(
    PASSWORD_CHANGE_RESPONSES,
    400,
    401,
)
# Administrator role assignment
add_error_responses(
    ROLE_ASSIGNMENT_RESPONSES,
    400,
    401,
    403,
    404,
    409,
)
