# Module 16 — Final Project Checkpoint

## Project

IT Helpdesk and Ticketing System

## Objective

Review the implementation delivered through Modules 1–15, identify remaining functional and security gaps, verify existing functionality and prepare the application for final delivery.

## Checkpoint 1 — Data Model & Authentication

### Domain Adaptation

The reference TaskFlow project has been adapted to the Helpdesk domain.

| Reference entity | Helpdesk equivalent |
|---|---|
| User | User |
| Container / Project | Department |
| Membership / ProjectMember | User.department_id |

## Checkpoint 2 — Containers, Membership & Permissions

### Domain-Specific Membership Model

Departments are centrally managed organizational resources.

Users belong to a department through `User.department_id`. Ticket access is determined by role, ownership and agent assignment rather than department membership alone.

Requesters can raise tickets for support departments other than their own.

### Permission Matrix

| Action | Admin | Assigned Agent | Requester/Owner | Unrelated User |
|---|---|---|---|---|
| View existing ticket | Yes | Yes | Yes | No |
| Create own ticket | Yes | Yes | Yes | Yes |
| Update requester-controlled fields | Conditional | No | Conditional | No |
| Change actual priority | Yes | No | No | No |
| Assign or reassign agent | Yes | No | No | No |
| Change status | Yes | Yes | No | No |
| Delete ticket | Yes | No | Conditional | No |
| View public comments | Yes | Yes | Yes | No |
| Add public comments | Yes | Yes | Yes | No |
| Access internal comments | Yes | Yes | Staff role required | No |

Requester-controlled fields can be modified only when the ticket belongs to the current user and is open and unassigned.

Agents creating their own tickets also receive applicable requester permissions.

### Authorization Response Policy

- HTTP 401: Missing or invalid authentication.
- HTTP 403: Forbidden role or field-level operation.
- HTTP 404: Missing, deleted or inaccessible ticket.
- HTTP 422: Invalid agent assignment or incompatible department.

The application intentionally conceals inaccessible ticket resources using HTTP 404. This differs from the reference specification's HTTP 403 requirement and is subject to mentor approval.

### Database Integrity Audit

The audit identified two historical tickets with inconsistent category and department values.

| Audit | Initial result |
|---|---|
| Category-department mismatch | 2 records |
| Agent-department mismatch | 0 records |
| Assigned users without agent role | 0 records |
| Self-assigned tickets | 0 records |
| Unresolved, non-deleted tickets assigned to inactive agents | 0 records |

The current API correctly maintains category-department consistency in the tested creation and update scenarios. The original cause of the historical inconsistencies was not established.

### Historical Data Repair

A guarded maintenance script was prepared:

`scripts/maintenance/repair_checkpoint2_tickets.sql`

The repair strategy preserves existing categories, derives the correct department and removes incompatible agent assignments where necessary.

Ticket 6 requires reassignment and is returned to under_review. Ticket 7 retains its soft-deleted state.

The repair preview was successful, with zero remaining category-department or agent-department inconsistencies.

Database backups were created before permanent modifications.

### Database-Level Integrity Protection

Added a composite unique constraint:

`uq_categories_id_department_id`

Added a composite foreign key:

`fk_tickets_category_department`

The composite foreign key enforces:

`tickets(category_id, department_id) → categories(id, department_id)`

Alembic revision: `269eebd9bb24`

The migration rejects existing inconsistent data rather than silently changing historical ticket records.

Agent-department compatibility and agent-role validation remain application-level business rules.

### Additional Regression Tests

Added eight tests covering:

1. Department consistency during category updates.
2. Department consistency during ticket creation.
3. Requester restrictions on assigned ticket modifications.
4. Cross-department agent assignment rejection.
5. Simultaneous category and incompatible agent assignment rejection.
6. Simultaneous category and compatible agent assignment acceptance.
7. Database rejection of inconsistent ticket insertion.
8. Database rejection of inconsistent ticket updates.

### Test Results

| Verification | Result |
|---|---|
| Initial permission test suite | 233 passed |
| Previous regression baseline | 423 passed |
| New checkpoint tests | 8 passed |
| Final regression suite | 431 passed |

### Status

Automated permission and database integrity verification passed.

Permanent data repair and deployment migration verification must be recorded before submission. Domain-specific permission adaptations remain subject to mentor approval.