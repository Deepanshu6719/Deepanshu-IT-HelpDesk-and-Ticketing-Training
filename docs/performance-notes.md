# Module 15 — Performance & Scalability

## 1. Objective

Improve the performance and scalability of the IT Helpdesk and Ticketing API through SQL query profiling, eager loading, PostgreSQL indexing, configurable connection pooling and concurrent load testing.

## 2. SQL Query Profiling

Implemented a reusable SQLAlchemy query profiler in `core/query_profiler.py`.

The profiler records:

- Executed SQL statement count.
- Total SQL cursor execution duration.
- Average SQL execution duration.
- Executed SQL statements without bound parameters.

Event listeners are removed automatically after profiling.

## 3. N+1 Query Investigation

The existing ticket-list endpoint already used `selectinload()` for related entities.

Initial measurements confirmed that the SQL statement count remained constant as the number of returned tickets increased.

| Tickets returned | SQL statements |
|---:|---:|
| 1 | 9 |
| 10 | 9 |
| 50 | 9 |

An isolated test reproduced the N+1 problem using the existing Ticket and User models.

| Tickets | Lazy loading | Eager loading |
|---:|---:|---:|
| 1 | 2 | 2 |
| 10 | 11 | 2 |
| 50 | 51 | 2 |

The comparison tests verify identical results and assert the expected query counts.

The working production endpoint was not deliberately degraded to reproduce the problem.

## 4. Authentication Query Optimization

The authentication dependency previously retrieved role assignments and role information through separate lazy-loading queries.

Updated `get_current_user()` to eagerly load role assignments and their associated roles using `joinedload()`.

| Tickets | Before | After |
|---:|---:|---:|
| 1 | 9 | 7 |
| 10 | 9 | 7 |
| 50 | 9 | 7 |

Results:

- 22.2% reduction in recorded SQL statements.
- 25% reduction in application SELECT statements, excluding the test savepoint.
- Existing authentication, session validation and authorization rules preserved.

A query-count regression budget prevents unexpected increases in SQL statements for the tested unassigned-ticket scenario.

## 5. Performance Testing Dataset

Created an isolated PostgreSQL database named `helpdesk_perf`.

The synthetic dataset was generated using `scripts/performance/seed.sql`.

| Entity | Dataset size |
|---|---:|
| Departments | 5 |
| Categories | 10 |
| Users | 1,051 |
| Tickets | 100,000 |
| Active tickets | 90,000 |
| Soft-deleted tickets | 10,000 |
| Ticket comments | 200,000 |

The seed script includes database safety checks, transaction handling and foreign-key-compatible data generation.

The normal application database is not used for synthetic performance testing.

## 6. PostgreSQL Index Optimization

Before optimization, PostgreSQL performed sequential scans and sorting for frequently accessed ticket and comment queries.

Added four indexes:

- `ix_tickets_active_created_id`
- `ix_tickets_active_requester_created_id`
- `ix_tickets_active_assigned_created_id`
- `ix_ticket_comments_ticket_created_id`

Ticket indexes are partial indexes excluding soft-deleted tickets.

Alembic migration: `575b4819a5bc`.

### EXPLAIN ANALYZE Results

| Query | Before | After | Reduction |
|---|---:|---:|---:|
| Admin ticket list | 41.043 ms | 0.132 ms | 99.68% |
| Requester ticket list | 26.683 ms | 0.104 ms | 99.61% |
| Ticket comments | 27.810 ms | 0.065 ms | 99.77% |
| Pagination count | 52.542 ms | 32.093 ms | 38.92% |

The optimized agent query executed in 0.376 ms. Its original baseline used a different agent, so a direct speedup comparison is not valid.

### Shared Buffer Usage

| Query | Before | After |
|---|---:|---:|
| Admin ticket list | 2,224 | 4 |
| Requester ticket list | 2,175 | 13 |
| Ticket comments | 2,212 | 5 |
| Pagination count | 2,175 | 348 |

PostgreSQL selected index scans for ticket and comment retrieval and an index-only scan for the pagination count.

Additional index storage was approximately 17.5 MiB.

The assigned-ticket index has not yet demonstrated an independent performance benefit and should be monitored during future workloads.

These results represent individual SQL execution measurements rather than complete API response-time improvements.

## 7. Database Connection Pooling

Made SQLAlchemy connection pooling configurable through environment variables.

| Setting | Value |
|---|---:|
| DB_POOL_SIZE | 5 |
| DB_MAX_OVERFLOW | 5 |
| DB_POOL_TIMEOUT | 3 seconds |
| DB_POOL_RECYCLE | 1,800 seconds |

Connection pre-ping remains enabled.

With two Gunicorn workers, the maximum theoretical API connection capacity is 20 PostgreSQL connections.

Database connection limits must be considered when increasing worker or replica counts.

## 8. Locust Load Testing

Implemented a reusable workload in `scripts/performance/locustfile.py`.

### Test Configuration

- Two Gunicorn workers.
- Isolated PostgreSQL performance database.
- Redis database 14.
- Real JWT authentication.
- Administrator, agent and requester roles.
- Two-minute benchmark duration per run.
- Five simulated users spawned per second.
- User wait time of one to three seconds.

### Workload Distribution

| Endpoint | Task weight |
|---|---:|
| GET /api/v1/tickets | 50% |
| GET /api/v1/tickets/{id} | 30% |
| GET /api/v1/tickets/{id}/comments | 20% |

### Load Test Results

| Metric | 20 users | 50 users |
|---|---:|---:|
| Total requests | 1,208 | 2,928 |
| Failed requests | 0 | 0 |
| Failure rate | 0% | 0% |
| Average latency | 9.28 ms | 9.40 ms |
| Median latency | 8 ms | 8 ms |
| P90 latency | 13 ms | 13 ms |
| P95 latency | 15 ms | 15 ms |
| P99 latency | 24 ms | 28 ms |
| Requests per second | 10.15 | 24.57 |

A total of 4,136 requests were successfully handled across both benchmarks.

Throughput increased approximately 2.42 times while P95 latency remained unchanged.

All defined HTTP latency and request failure targets were satisfied.

## 9. Horizontal Scalability

The application stores authentication sessions and persistent data in PostgreSQL. Redis provides shared caching and rate limiting.

API instances can therefore share application state without depending on process-local authentication sessions.

Verification scripts:

- `scripts/performance/verify_scaling.py`
- `scripts/performance/verify_session_revocation.py`

Verification targets:

- Access tokens accepted by independently running API instances.
- Consistent ticket access across instances.
- Shared Redis category cache.
- Session revocation enforced across instances.

Manual verification results must be recorded before final submission.

## 10. Regression Testing



## Dashboard Cache Benchmark — Module 16 Checkpoint 4

Date: November 27, 2026

### Environment

- PostgreSQL database: `helpdesk_perf`
- Total tickets: 100,000
- Active tickets: 90,000
- Soft-deleted tickets: 10,000
- Redis database: 13
- API server: Uvicorn, localhost port 8002
- Benchmark user: Performance administrator
- Dashboard cache TTL: 60 seconds
- Benchmark script: `scripts/performance/benchmark_dashboard.py`

### Methodology

Executed five warm-up requests followed by 50 paired cache MISS and cache HIT measurements.

Each iteration invalidated the dashboard generation, retrieved a fresh dashboard response, and immediately repeated the request using the cached result.

The same HTTP connection was reused, and response consistency was checked for every pair.

### Results

| Metric | Cache MISS | Cache HIT |
|---|---:|---:|
| Requests | 50 | 50 |
| Mean latency | 20.889 ms | 4.238 ms |
| Median latency | 20.738 ms | 4.088 ms |
| P95 latency | 22.368 ms | 5.418 ms |
| Minimum latency | 19.065 ms | 3.350 ms |
| Maximum latency | 30.578 ms | 6.061 ms |

- Median latency reduction: 80.29%.
- Median speedup: 5.07x.
- Response consistency: PASSED.

### Conclusion

Redis caching significantly reduced dashboard response latency by avoiding repeated PostgreSQL ticket aggregation.

Authentication and session validation remain active on every request.

Generation-based invalidation prevents obsolete cache entries from being reused by subsequent requests. Obsolete dashboard entries expire automatically through their configured TTL.

### Limitations

The benchmark measures sequential HTTP request latency in a local development environment. It does not measure concurrent dashboard throughput or distributed deployment performance.

Cache invalidation and PostgreSQL commits are not atomic. Failed invalidation can temporarily leave stale dashboard statistics until cache expiration.

Aggregate-query avoidance on cache HIT is supported by automated service invocation tests; SQL query counts were not independently measured during this HTTP benchmark.