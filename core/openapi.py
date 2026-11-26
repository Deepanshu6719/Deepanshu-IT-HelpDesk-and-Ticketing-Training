API_TITLE = "IT Helpdesk and Ticketing API"

API_VERSION = "1.0.0"

API_DESCRIPTION = """
## Overview

A REST API for managing internal IT support requests,
ticket assignments, departments, categories and users.

## Authentication

The API uses JWT-based authentication with access tokens,
refresh token rotation and session management.

## Roles and permissions

- **Requester:** Create and manage personal support tickets.
- **Agent:** Manage assigned tickets and add internal comments.
- **Admin:** Manage users, roles, departments, categories
  and ticket assignments.

## API versioning

All business endpoints are available under `/api/v1`.

## Observability

Every HTTP request includes a unique `X-Request-ID`
response header for request correlation and troubleshooting.
"""

OPENAPI_TAGS = [
    {
        "name": "Authentication",
        "description": "Login, token refresh and session logout.",
    },
    {
        "name": "Tickets",
        "description": "Create, retrieve, update and soft-delete support tickets.",
    },
    {
        "name": "Comments",
        "description": "Manage public and internal ticket comments.",
    },
    {
        "name": "Users",
        "description": "User management, account status and password changes.",
    },
    {
        "name": "Admin",
        "description": "Administrative role management operations.",
    },
    {
        "name": "Agents",
        "description": "Discover active support agents by department.",
    },
    {
        "name": "Departments",
        "description": "Manage organizational departments.",
    },
    {
        "name": "Categories",
        "description": "Manage department-specific support categories.",
    },
    {
        "name": "Health",
        "description": "Application liveness and dependency readiness checks.",
    },
]
