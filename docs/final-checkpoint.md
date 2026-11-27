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
### Final Quality and Security Verification

Final verification completed on November 27, 2026.

| Verification | Result |
|---|---|
| Automated regression suite | 482 passed |
| Regression execution time | 13.44 seconds |
| Warnings treated as errors | Passed |
| Ruff linting | Passed |
| Ruff formatting | 131 files compliant |
| Python dependency integrity | Passed |
| Requirements vulnerability audit | No known vulnerabilities found |
| Installed dependency vulnerability audit | No known vulnerabilities found |
| Git history secret scanning | 29 commits scanned; no leaks detected |
| Staged documentation secret scanning | No leaks detected |
| Git whitespace validation | Passed |

These results confirm that the final implementation passed the configured automated quality and security checks.

The security scans do not guarantee the absence of undiscovered vulnerabilities or replace infrastructure-level security assessments.

## Checkpoint 5 — Production Readiness and Final Integration

### Objective

Verify that the complete IT Helpdesk application can be securely deployed from a fresh repository clone and that its business workflows operate correctly using real infrastructure services.

### Existing Production-Oriented Implementation

The application already provides:

- Versioned business endpoints under `/api/v1`.
- Consistent success and error response envelopes.
- OAuth2-compatible authentication token responses.
- Strict request schema validation.
- Object-level authorization and mass assignment protection.
- Configurable CORS and security response headers.
- PostgreSQL performance indexes and connection pooling.
- SQLAlchemy eager loading.
- Redis caching and rate limiting.
- Celery background task processing.
- Structured logging and Prometheus metrics.
- Automated CI quality checks.

These features were retained and verified during the final checkpoint.

### Automatic Database Initialization

Implemented automatic administrator provisioning through `scripts/init_db.py`.

The initialization process:

1. Acquires a PostgreSQL transaction-level advisory lock.
2. Creates missing administrator and agent roles.
3. Checks whether an active administrator already exists.
4. Creates the initial IT department when required.
5. Validates administrator credentials.
6. Hashes the administrator password.
7. Creates the administrator account.
8. Assigns administrator and agent roles.
9. Commits the initialization transaction.

Failed initialization rolls back database changes.

Both interactive and non-interactive initialization are supported.

Existing users are not silently promoted to administrators.

### Docker Deployment Improvements

The Docker Compose deployment contains six services:

| Service | Responsibility |
|---|---|
| db | PostgreSQL database |
| redis | Redis cache and Celery message broker |
| migrate | Execute Alembic migrations |
| bootstrap | Initialize the database and first administrator |
| app | FastAPI application |
| worker | Celery background worker |

The migration service waits for PostgreSQL readiness.

The bootstrap service waits for successful migration completion.

The application and worker wait for successful bootstrap completion and their configured service dependencies.

The application binds to the loopback interface by default.

The application port is configurable through `APP_PORT`.

PostgreSQL and Redis use persistent named Docker volumes.

### Bootstrap Automated Tests

Added ten automated tests covering:

- Initial administrator creation.
- Repeated initialization without duplicate records.
- Preservation of existing administrator credentials.
- Missing administrator email.
- Missing administrator password.
- Invalid administrator email.
- Password below the minimum length.
- Password above the maximum length.
- Rejection of silent promotion of an existing requester.
- Transaction rollback after role assignment failure.

| Verification | Result |
|---|---:|
| Checkpoint 4 baseline | 472 passed |
| Additional bootstrap tests | 10 passed |
| Checkpoint 5 regression suite | 482 passed |

### Existing Deployment Upgrade

Verified the updated Docker Compose deployment against an existing initialized database.

Results:

- Existing database records preserved.
- Existing administrator preserved.
- Alembic migration revision verified.
- Bootstrap completed successfully without creating another administrator.
- FastAPI application started successfully.
- Celery worker started successfully.
- Health endpoint returned HTTP 200.
- Readiness endpoint returned HTTP 200.

### Fresh Clone Deployment

Created an independent repository clone and Docker Compose project.

| Property | Value |
|---|---|
| Docker Compose project | helpdesk-fresh-verification |
| Application port | 8003 |
| Database | helpdesk_fresh |
| Database user | helpdesk_fresh_user |
| PostgreSQL volume | Independent |
| Redis volume | Independent |

The original application on port 8001 remained operational during verification.

The complete twelve-revision Alembic migration history executed successfully against an empty PostgreSQL database.

Final migration revision: `269eebd9bb24`.

Initial database state:

| Entity | Count |
|---|---:|
| Departments | 1 |
| Roles | 2 |
| Users | 1 |
| User-role assignments | 2 |
| Tickets | 0 |

Both migration and bootstrap containers exited successfully with exit code 0.

FastAPI and Celery started successfully without manual database initialization.

### Docker Environment Configuration Issue and Resolution

The initial fresh deployment failed because exported shell environment variables overrode values from the fresh deployment's `.env` file during Docker Compose interpolation.

PostgreSQL and the Python services consequently received inconsistent database credentials.

The issue was diagnosed by comparing resolved service configurations without exposing credentials.

Resolution:

- Removed conflicting exported shell variables.
- Recreated only the disposable fresh verification volumes.
- Explicitly configured database username, password and database name for all database-consuming services.
- Added required-variable validation to Docker Compose interpolation.
- Verified normal configuration consistency.
- Verified consistency under synthetic exported environment variable overrides.

All twelve credential comparisons passed across the migration, bootstrap, application and worker services.

Configuration fix commit: `a0b7d4a`.

Docker Compose shell environment precedence remains applicable. The fix ensures consistency across services but does not prevent unintended shell overrides.

### Bootstrap Idempotency and Concurrent Execution

Repeated initialization against an existing administrator completed successfully.

Two independent bootstrap processes were also executed concurrently.

Both processes returned exit code 0 and logged that initialization was skipped because an active administrator already existed.

Database verification confirmed:

| Entity | Count before | Count after |
|---|---:|---:|
| Users | 1 | 1 |
| Roles | 2 | 2 |
| Departments | 1 | 1 |
| User-role assignments | 2 | 2 |

No duplicate records were created.

The verification covers concurrent initialization against an existing administrator. Simultaneous first-administrator creation against an empty database was not independently integration-tested.

### Multi-User Integration Environment

Provisioned four users through the deployed REST API.

| User ID | Effective role | Department |
|---:|---|---|
| 1 | Administrator and Agent | IT |
| 2 | Requester | IT |
| 3 | Agent | IT |
| 4 | Requester | Finance |

Created the Laptop Support category in the IT department.

All user provisioning and category creation operations succeeded.

Temporary integration credentials were randomly generated and stored in Git-ignored local files with restricted permissions.

### Complete Ticket Lifecycle Verification

Executed the complete ticket workflow through the running Docker application.

| Operation | Result |
|---|---|
| Requester creates ticket | Passed |
| Initial status is open | Passed |
| Administrator reviews ticket | Passed |
| Status changes to under_review | Passed |
| Administrator assigns agent | Passed |
| Status changes to in_progress | Passed |
| Assigned agent resolves ticket | Passed |
| Administrator closes ticket | Passed |

Final ticket state:

| Property | Value |
|---|---|
| Ticket ID | 1 |
| Requester ID | 2 |
| Assigned agent ID | 3 |
| Department ID | 1 |
| Requested priority | high |
| Operational priority | high |
| Status | closed |
| Soft-deleted | false |

The final record was independently verified in PostgreSQL.

### Real Celery Notification Execution

Verified real notification task execution through the Redis message broker and Docker Celery worker.

| Event | Successful tasks |
|---|---:|
| Ticket creation | 2 |
| Ticket assignment | 2 |
| Total | 4 |

All four tasks had distinct task identifiers.

HTTP request-to-Celery task correlation was verified using propagated request identifiers.

Creation request ID:

`0a664817-b6bf-4ff7-9b79-ff4aae3c5af8`

Assignment request ID:

`24127ea6-ad46-48b5-a886-e804cd329054`

The worker executed actual background tasks. External email delivery remains simulated.

Recipient-selection behavior is covered by application tests; recipient addresses were not independently verified through worker logs.

### Live Authorization and Security Verification

Verified authorization using four real authenticated users.

| Operation | HTTP status | Result |
|---|---:|---|
| Administrator views ticket | 200 | Passed |
| Requester views own ticket | 200 | Passed |
| Assigned agent views ticket | 200 | Passed |
| Outsider views unauthorized ticket | 404 | Passed |
| Outsider modifies unauthorized ticket | 404 | Passed |
| Outsider deletes unauthorized ticket | 404 | Passed |
| Agent modifies operational priority | 403 | Passed |
| Requester resolves assigned ticket | 404 | Passed |
| Administrator attempts mass assignment of requester ID | 422 | Passed |
| Requester creates internal comment | 403 | Passed |
| Outsider retrieves ticket comments | 404 | Passed |
| Login rate limit exceeded | 429 | Passed |

Rejected mutations preserved the original ticket state.

Authentication succeeded again after the rate-limit window expired.

The application intentionally uses HTTP 404 for inaccessible ticket resources to reduce resource existence disclosure.

### Public and Internal Comment Verification

Created three comments through the deployed application.

- One public requester comment.
- One internal agent comment.
- One public agent comment.

| User | Visible comments | Internal comments visible |
|---|---:|---:|
| Administrator | 3 | 1 |
| Assigned agent | 3 | 1 |
| Requester | 2 | 0 |
| Outsider | Access denied | Access denied |

PostgreSQL verification confirmed exactly three comment records.

### Dashboard Integration Verification

Verified dashboard statistics for all four users.

Before resolution:

- Administrator visible ticket count: 1.
- Requester visible ticket count: 1.
- Assigned agent visible ticket count: 1.
- Outsider visible ticket count: 0.

After agent resolution, authorized dashboard responses correctly reflected the resolved status.

After administrator closure, authorized dashboard responses correctly reflected the closed status.

Outsider dashboard statistics remained isolated throughout the workflow.

Dashboard cache invalidation was verified after both status mutations.

The previously completed performance benchmark demonstrated:

| Metric | Cache miss | Cache hit |
|---|---:|---:|
| Median latency | 20.738 ms | 4.088 ms |
| P95 latency | 22.368 ms | 5.418 ms |

Median speedup: 5.07x.

Median latency reduction: 80.29%.

These performance results were obtained during Checkpoint 4 using the dedicated performance dataset, not the small fresh deployment dataset.

### Bootstrap Credential Cleanup

Removed initial administrator provisioning credentials from the fresh deployment's `.env` file after successful initialization.

Recreated the Docker containers without deleting persistent volumes.

Verified that bootstrap administrator email and password variables were absent from the environments of:

- Migration container.
- Bootstrap container.
- Application container.
- Worker container.

Bootstrap successfully skipped administrator creation.

The existing administrator continued authenticating successfully.

Removing bootstrap credentials from container environments does not rotate the administrator password.

Temporary verification credentials require separate cleanup.

### Persistence After Container Recreation

Verified the following database records after all six containers were recreated:

| Entity | Final count |
|---|---:|
| Users | 4 |
| Departments | 2 |
| Categories | 1 |
| Tickets | 1 |
| Ticket comments | 3 |

The ticket remained closed and assigned to agent ID 3.

Administrator authentication and dashboard statistics remained functional.

Both the original and fresh deployments returned successful readiness responses.

### Documentation

Created a comprehensive repository README covering:

- System architecture.
- Database entities and relationships.
- Authentication and authorization.
- Permission matrix.
- Ticket lifecycle.
- REST API endpoints.
- Response formats.
- Docker deployment.
- Environment configuration.
- Administrator bootstrap.
- Local development.
- Automated testing.
- Security.
- Caching and rate limiting.
- Celery background processing.
- Observability.
- Performance benchmarks.
- Known limitations and future improvements.

### Database Changes

No new Alembic migration was required during Checkpoint 5.

The final database revision remains `269eebd9bb24`.

### Domain Adaptations

The original training checkpoint requirements were adapted to an internal IT helpdesk system.

| Reference concept | Helpdesk implementation |
|---|---|
| Project or container | Department |
| Container membership | User department association |
| Task | Support ticket |
| Task assignment | Administrator assigns support agent |
| Task comments | Public and internal ticket comments |

Departments are managed by administrators rather than ordinary users.

Public registration and user-managed invitations are intentionally not implemented.

Ticket access is determined by roles, ownership and assignment rather than department membership alone.

Unauthorized ticket access returns HTTP 404 rather than the reference checkpoint's HTTP 403 expectation.

These adaptations preserve the helpdesk's business requirements and require mentor acceptance as alternatives to the reference domain.

### Known Limitations and Future Improvements

- External email delivery remains simulated.
- PostgreSQL commits and Celery task publication are not atomic.
- PostgreSQL commits and Redis cache invalidation are not atomic.
- Global dashboard invalidation can invalidate unaffected users' cached data.
- Cache stampede protection is not implemented.
- Concurrent creation of the first administrator has not been independently integration-tested.
- Authentication rate limiting requires appropriate trusted-proxy configuration for reverse-proxy deployments.
- General-purpose idempotency-key processing remains a documented design rather than an implemented feature.
- Managed secret storage and production TLS termination require additional infrastructure.
- Backup archives were inspected, but a complete independent backup restoration drill was not verified.
- Infrastructure and container image vulnerability scanning remain additional operational tasks.
- Performance measurements are local benchmark results and do not establish production capacity.

### Retrospective — Hardest Implementation Challenges

The main engineering challenges included maintaining consistent authorization across ticket operations, implementing secure refresh token rotation and session revocation, preventing stale role-scoped dashboard data, enforcing category-department consistency at the database level, and making Docker deployment reproducible.

A particularly important deployment challenge was diagnosing the inconsistent database credentials caused by Docker Compose environment variable precedence.

Resolving these issues required application-level validation, database constraints, automated regression tests, isolated deployment verification and careful examination of real service logs.

### Retrospective — What Could Be Improved

A future iteration could introduce a transactional outbox for reliable task publication, external email integration, more targeted cache invalidation, stronger concurrent execution testing, managed secrets and more comprehensive deployment automation.

A stronger operational verification process would include automated backup restoration tests, container vulnerability scanning, distributed load testing and production-like monitoring.

### Mentor Demonstration Plan

The final demonstration should cover:

1. Repository architecture and database entity relationships.
2. Authentication, refresh token rotation and session revocation.
3. Role-based and object-level authorization.
4. Ticket creation, review, assignment, resolution and closure.
5. Internal comment visibility and unauthorized access rejection.
6. Real Celery task execution and request correlation.
7. Dashboard cache behavior and invalidation.
8. Automated testing and performance results.
9. Fresh Docker deployment and administrator bootstrap.
10. Known limitations, domain adaptations and future improvements.

### Status

Application implementation, automated regression testing, security verification, fresh Docker deployment, end-to-end business integration and final documentation have been completed successfully.

All 482 automated tests passed, and the configured dependency and secret scans reported no findings.

Final CI approval, mentor acceptance of domain adaptations and pull request merge remain pending.