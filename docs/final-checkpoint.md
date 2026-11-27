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

## Checkpoint 3 — Ticket CRUD, Pagination & Filtering

### Existing Implementation

The Helpdesk application provides complete ticket CRUD functionality through versioned API endpoints.

| Method | Endpoint | Purpose |
|---|---|---|
| POST | /api/v1/tickets | Create a ticket |
| GET | /api/v1/tickets | List accessible tickets |
| GET | /api/v1/tickets/{id} | Retrieve a ticket |
| PATCH | /api/v1/tickets/{id} | Partially update a ticket |
| DELETE | /api/v1/tickets/{id} | Soft-delete a ticket |

### Partial Update Verification

Verified that PATCH updates only explicitly provided fields while preserving omitted business fields.

The updated_at timestamp is excluded from unchanged-field assertions because successful modifications are expected to update it.

Explicit null values are rejected for non-nullable requester-controlled fields.

Empty PATCH requests are rejected under the existing validation contract.

### Pagination and Filtering

Verified that pagination works together with:

- Status filtering.
- Priority filtering.
- Category filtering.
- Department filtering.
- Case-insensitive search.

Combined filtering tests confirmed:

- Matching records are returned across consecutive pages.
- No duplicate or missing matching records occur for an unchanged dataset.
- The total represents all accessible matching records before pagination.
- Requests beyond the available page range return an empty items list while preserving the correct total.
- Soft-deleted tickets are excluded from filtered results and totals.

### Authorization and Data Isolation

Verified that unauthorized tickets do not appear in filtered results or pagination totals.

Users from the same department cannot automatically access each other's tickets.

Users from different departments cannot access unrelated tickets merely by guessing their IDs.

Ticket visibility continues to follow the existing Helpdesk permission model:

- Administrators can access all non-deleted tickets.
- Agents can access assigned tickets and tickets they requested.
- Requesters can access their own tickets.

Existing object-level authorization and database-state preservation tests remain passing.

### Additional Regression Tests

Added `tests/test_checkpoint_crud.py` containing nine test cases:

1. Partial title update preserves omitted business fields.
2. Explicit null title rejection.
3. Explicit null description rejection.
4. Explicit null category rejection.
5. Explicit null requested priority rejection.
6. Combined search, filtering and pagination.
7. Authorization-aware filtered results and totals.
8. Pagination beyond available filtered results.
9. Soft-deleted ticket exclusion from filtered results.

### Test Results

| Verification | Result |
|---|---|
| Previous regression baseline | 431 passed |
| Existing targeted ticket tests | 115 passed |
| New checkpoint tests | 9 passed |
| Final regression suite | 440 passed |

### Database and Application Changes

No application code changes or database migrations were required.

Existing CRUD, filtering, pagination and authorization implementations satisfied the tested requirements.

### Status

Technical verification completed successfully. Final acceptance remains subject to CI verification and mentor review.

## Checkpoint 4 — Background Jobs, Caching & Observability

### Dashboard Implementation

Implemented the authenticated dashboard endpoint:

`GET /api/v1/dashboard/me`

The dashboard provides:

- Total accessible non-deleted tickets.
- Ticket counts by status.
- Ticket counts by actual priority.
- Assigned and unassigned ticket counts.

The dashboard and ticket-list endpoint share reusable ticket visibility filters through `core/ticket_scope.py`.

Dashboard statistics are calculated using a single PostgreSQL aggregate query implemented in `services/dashboard.py`.

### Redis Caching

Implemented user-specific dashboard caching using the following key structure:

`helpdesk:dashboard:v1:{generation}:{scope}:{user_id}`

- Dashboard cache TTL: 60 seconds.
- Cache isolation by user ID and effective role.
- Authentication and session validation occur before cache access.
- PostgreSQL fallback when dashboard caching is unavailable.
- Recovery from malformed or schema-invalid cached data.

### Cache Invalidation

Implemented UUID-based generation invalidation following successful database commits for:

- Ticket creation, updates and soft deletion.
- Agent assignment, reassignment and unassignment.
- Ticket status and priority changes.
- User role assignment.
- User activation and deactivation.

Obsolete cache generations are no longer used by subsequent requests. Their response keys expire automatically.

A deterministic race-condition test verifies that writing data into an obsolete generation does not overwrite the current dashboard cache.

### Performance Verification

Benchmarked the administrator dashboard using 100,000 tickets, including 90,000 non-deleted tickets.

The benchmark executed 50 paired cache MISS and HIT measurements after five warm-up requests.

| Metric | Cache MISS | Cache HIT |
|---|---:|---:|
| Mean latency | 20.889 ms | 4.238 ms |
| Median latency | 20.738 ms | 4.088 ms |
| P95 latency | 22.368 ms | 5.418 ms |

- Median latency reduction: 80.29%.
- Median speedup: 5.07x.
- Response consistency: PASSED.

Detailed methodology and results are recorded in `docs/performance-notes.md`.

### Real Celery Background Execution

Started an isolated Celery worker using Redis broker database 12.

Created a verification ticket through the running API.

- Ticket ID: 100001.
- HTTP response: 201 Created.
- Notification tasks received: 2.
- Notification tasks successfully executed: 2.
- Distinct Celery task IDs: verified.
- Structured JSON worker logs: verified.
- HTTP-to-Celery request ID propagation: verified.

The notification tasks execute through the real Redis broker and Celery worker. External email delivery remains simulated.

### Observability Verification

Verified:

- Structured HTTP request logging.
- Unique X-Request-ID response headers.
- Request ID propagation into Celery tasks.
- Liveness endpoint: GET /health.
- Readiness endpoint: GET /ready.
- Prometheus endpoint: GET /metrics.
- HTTP request counters.
- HTTP request duration histograms.
- Normalized route labels.
- Successful and failed authentication request metrics.

### Live Cache Invalidation Verification

Created and subsequently soft-deleted verification ticket 100001 using the running API.

- Active tickets after creation: 90,001.
- Ticket deletion response: HTTP 204.
- Active tickets after deletion: 90,000.
- Database soft-delete flag and deletion timestamp: verified.
- Updated dashboard statistics after deletion: verified.

The verification record remains soft-deleted in the performance database.

### Automated Tests

| Verification | Result |
|---|---:|
| Checkpoint 3 baseline | 440 passed |
| Dashboard functionality tests | 11 passed |
| Dashboard caching tests | 21 passed |
| Final regression suite | 472 passed |

Additional tests cover authorization, aggregate consistency, cache HIT behavior, TTL, cache isolation, mutation invalidation, failed mutations, role promotion, inactive users, Redis failures, corrupted payloads and generation recovery.

### Known Limitations

- PostgreSQL commits and Redis invalidation are not atomic.
- Failed invalidation can temporarily leave stale aggregate statistics.
- Cache expiration provides eventual recovery from failed invalidation.
- Global generation invalidation prioritizes correctness and simplicity over targeted cache efficiency.
- The concurrency test simulates a specific race condition rather than performing a full concurrent stress test.
- The benchmark measures sequential local HTTP latency, not distributed throughput.
- Notification delivery is simulated.
- Real assignment notification execution remains part of the final end-to-end verification.

### Database Changes

No new database migrations were required for the dashboard.

The existing performance database was upgraded to revision `269eebd9bb24`, and both category-department integrity constraints were validated.

### Status

Technical verification completed successfully. Final acceptance remains subject to CI and mentor review.