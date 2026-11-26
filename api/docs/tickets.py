from api.docs.common import success_example_response
from api.docs.errors import (
    FORBIDDEN_RESPONSE,
    NOT_FOUND_RESPONSE,
    UNAUTHORIZED_RESPONSE,
)

TICKET_EXAMPLE = {
    "id": 101,
    "title": "Laptop cannot connect to Wi-Fi",
    "description": "The laptop disconnects from the office Wi-Fi repeatedly.",
    "category": {
        "id": 7,
        "name": "Wi-Fi Connectivity",
    },
    "requested_priority": "high",
    "priority": "medium",
    "status": "under_review",
    "assigned_to": {
        "id": 3,
        "email": "agent@example.com",
    },
    "requester_id": 5,
    "requester": {
        "id": 5,
        "email": "requester@example.com",
    },
    "created_at": "2026-11-26T06:00:00Z",
    "updated_at": "2026-11-26T06:15:00Z",
}

TICKET_CREATED_EXAMPLE = {
    **TICKET_EXAMPLE,
    "requested_priority": "high",
    "priority": "high",
    "status": "open",
    "assigned_to": None,
    "updated_at": "2026-11-26T06:00:00Z",
}

TICKET_LIST_EXAMPLE = {
    "total": 1,
    "page": 1,
    "limit": 10,
    "items": [TICKET_EXAMPLE],
}

TICKET_CREATE_EXAMPLES = {
    "network_issue": {
        "summary": "Office Wi-Fi connectivity issue",
        "value": {
            "title": "Laptop cannot connect to Wi-Fi",
            "description": "The laptop disconnects from the office Wi-Fi repeatedly.",
            "category": "Wi-Fi Connectivity",
            "priority": "high",
        },
    },
    "hardware_issue": {
        "summary": "Damaged laptop display",
        "value": {
            "title": "Laptop screen flickering",
            "description": "The laptop display flickers continuously during normal use.",
            "category": "Laptop Issue",
            "priority": "medium",
        },
    },
    "account_issue": {
        "summary": "Employee account access issue",
        "value": {
            "title": "Unable to access company email",
            "description": "My company email account rejects my login credentials.",
            "category": "Account Access",
            "priority": "urgent",
        },
    },
}

TICKET_UPDATE_EXAMPLES = {
    "admin_assignment": {
        "summary": "Admin assigns a ticket",
        "value": {
            "assigned_to": 3,
            "status": "under_review",
            "priority": "high",
        },
    },
    "agent_status_update": {
        "summary": "Assigned agent updates ticket status",
        "value": {
            "status": "in_progress",
        },
    },
    "requester_update": {
        "summary": "Requester updates an open and unassigned ticket",
        "value": {
            "title": "Laptop Wi-Fi connection unstable",
            "requested_priority": "high",
        },
    },
}


TICKET_LIST_RESPONSES = {
    200: success_example_response(
        "Accessible tickets retrieved successfully.",
        TICKET_LIST_EXAMPLE,
    ),
}

TICKET_CREATE_RESPONSES = {
    201: success_example_response(
        "Support ticket created successfully.",
        TICKET_CREATED_EXAMPLE,
    ),
}

TICKET_DETAIL_RESPONSES = {
    200: success_example_response(
        "Ticket retrieved successfully.",
        TICKET_EXAMPLE,
    ),
}

TICKET_UPDATE_RESPONSES = {
    200: success_example_response(
        "Ticket updated successfully.",
        TICKET_EXAMPLE,
    ),
}

TICKET_DELETE_RESPONSES = {
    204: {
        "description": "Ticket successfully soft-deleted.",
    },
}

TICKET_LIST_RESPONSES.update(
    {
        401: UNAUTHORIZED_RESPONSE,
        403: FORBIDDEN_RESPONSE,
    }
)

TICKET_CREATE_RESPONSES.update(
    {
        401: UNAUTHORIZED_RESPONSE,
    }
)

TICKET_DETAIL_RESPONSES.update(
    {
        401: UNAUTHORIZED_RESPONSE,
        404: NOT_FOUND_RESPONSE,
    }
)

TICKET_UPDATE_RESPONSES.update(
    {
        401: UNAUTHORIZED_RESPONSE,
        403: FORBIDDEN_RESPONSE,
        404: NOT_FOUND_RESPONSE,
    }
)

TICKET_DELETE_RESPONSES.update(
    {
        401: UNAUTHORIZED_RESPONSE,
        403: FORBIDDEN_RESPONSE,
        404: NOT_FOUND_RESPONSE,
    }
)
