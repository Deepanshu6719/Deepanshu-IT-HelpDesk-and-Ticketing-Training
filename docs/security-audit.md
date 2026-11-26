# Module 14 — Security Hardening Audit

## 1. Project Scope

Project: IT Helpdesk and Ticketing System

Framework: FastAPI

API version: v1

Database: PostgreSQL

Supporting services: Redis and Celery

This audit reviews the application's 26 business API operations, authentication mechanisms, authorization policies, request and response schemas, security configuration and Python dependencies.

## 2. OWASP API Security Top 10

| Risk | Implemented protection |
|---|---|
| API1 — Broken Object Level Authorization | Ticket ownership, agent assignment and administrator access checks |
| API2 — Broken Authentication | JWT validation, password hashing, refresh-token rotation, session revocation and login timing mitigation |
| API3 — Broken Object Property Level Authorization | Restrictive Pydantic request schemas, field-level permissions and explicit response schemas |
| API4 — Unrestricted Resource Consumption | Login rate limiting, refresh rate limiting, pagination limits and input validation |
| API5 — Broken Function Level Authorization | Administrator-only operations protected through RBAC dependencies |
| API8 — Security Misconfiguration | Explicit CORS allow-list, security headers, environment-based configuration and dependency scanning |
| API9 — Improper Inventory Management | Versioned business endpoints and OpenAPI documentation |

This is a targeted application security audit, not a complete assessment of every OWASP risk.

## 3. Endpoint Authorization Audit

All paths below are relative to /api/v1.

| Method | Endpoint | Authorization policy |
|---|---|---|
| POST | /auth/login | Valid credentials and active account |
| POST | /auth/refresh | Valid refresh token, active session and active account |
| POST | /auth/logout | Authenticated user's current session |
| GET | /tickets | Role-based ticket visibility |
| POST | /tickets | Authenticated user; ownership assigned by server |
| GET | /tickets/{id} | Owner, assigned agent or administrator |
| PATCH | /tickets/{id} | Object access and role-specific field permissions |
| DELETE | /tickets/{id} | Administrator or eligible ticket owner |
| GET | /tickets/{id}/comments | Ticket access and comment visibility restrictions |
| POST | /tickets/{id}/comments | Ticket access and internal-comment permissions |
| GET | /users | Administrator |
| POST | /users | Administrator |
| GET | /users/{id} | Administrator |
| PATCH | /users/{id}/status | Administrator |
| PATCH | /users/me/password | Authenticated user changing own password |
| POST | /admin/users/{id}/roles | Administrator |
| GET | /departments | Administrator |
| POST | /departments | Administrator |
| GET | /departments/{id} | Administrator |
| PATCH | /departments/{id} | Administrator |
| GET | /categories | Administrator |
| POST | /categories | Administrator |
| PATCH | /categories/{id} | Administrator |
| DELETE | /categories/{id} | Administrator |
| GET | /agents | Administrator |
| GET | /departments/{id}/agents | Administrator |

Dedicated regression tests verify cross-user access prevention, unauthorized modification prevention, unauthorized deletion prevention and scoped pagination metadata.

Inaccessible ticket objects return HTTP 404 to reduce object-existence disclosure.

## 4. Mass Assignment Protection

A shared StrictRequestModel uses Pydantic's extra="forbid" configuration.

Unexpected JSON request properties are rejected with HTTP 422.

Protected properties include:

- User identity, password hashes and token versions.
- Ticket ownership, department identifiers and soft-deletion metadata.
- Comment ownership and creation timestamps.
- Category and department identifiers.
- Session ownership, expiration and revocation metadata.

Role assignment, account status, ticket assignment, ticket priority and internal comments are controlled through designated operations and authorization policies.

There is no public signup endpoint. User creation is restricted to administrators.

## 5. Authentication Hardening

- Argon2id password hashing.
- Dummy password-hash verification for nonexistent accounts.
- Password verification for inactive accounts before rejection.
- Consistent invalid-credential responses.
- JWT signature, expiration and session validation.
- Refresh-token hashing and rotation.
- Refresh-token reuse detection.
- Revocation of existing sessions and refresh tokens after password changes.
- Token version increment after password changes.

Dummy password hashing mitigates account-enumeration timing differences but does not guarantee constant-time responses.

## 6. Rate Limiting

Redis-backed atomic fixed-window rate limiting is implemented.

| Endpoint | Limit | Window |
|---|---:|---:|
| Login | 5 requests per IP | 60 seconds |
| Refresh | 20 requests per IP | 60 seconds |

The endpoints use independent Redis counters with expiration.

Exceeded limits return HTTP 429.

Redis rate-limiting failures return HTTP 503.

## 7. Category Validation

- Inactive categories cannot be selected for ticket creation or category updates.
- Ambiguous category names are rejected rather than resolved arbitrarily.
- Existing category-name request contracts are preserved.

## 8. CORS Configuration

CORS origins are configured through environment variables.

- Explicit trusted origin allow-list.
- Wildcard origins rejected.
- Explicit permitted HTTP methods.
- Explicit permitted request headers.
- Credentialed CORS disabled.
- X-Request-ID exposed to trusted origins.

CORS is not a replacement for API authentication or authorization.

## 9. Security Headers

Reusable ASGI middleware applies:

- X-Content-Type-Options: nosniff
- X-Frame-Options: DENY
- Referrer-Policy: no-referrer
- Permissions-Policy: camera=(), microphone=(), geolocation=()
- Strict-Transport-Security when enabled for HTTPS requests.

Unhandled application errors also receive security headers.

HSTS remains disabled for local HTTP development.

## 10. Secrets Management

- Application credentials are loaded through environment configuration.
- The actual .env file is excluded from Git tracking.
- The .env.example file must contain placeholders only.
- Sensitive filenames were checked in tracked files and available Git history.
- An initial Gitleaks scan reported no detected leaks across 20 commits.
- JWT signing-secret rotation was performed as a security precaution, subject to configuration verification.
- Existing authentication sessions and refresh tokens were revoked in local and Docker application databases.
- Gitleaks scanned all locally available Git references.
- 20 commits were scanned, with no detected secret leaks.

Production and development environments should use separate credentials and signing keys.

## 11. Dependency Security

Security scanning tool: pip-audit 2.10.1.

The initial installed-environment audit reported 14 vulnerability entries affecting three packages.

| Package | Previous version | Remediated version |
|---|---|---|
| dnspython | 2.9.0 | 2.9.2 |
| opentelemetry-api | 1.45.1 | 1.45.2 |
| pip | 24.0 | 26.2 |

Related OpenTelemetry dependencies were upgraded to compatible versions.

Final local verification:

- pip check: no broken requirements found.
- Installed environment audit: no known vulnerabilities found.
- Production requirements audit: no known vulnerabilities found.
- Development requirements audit: no known vulnerabilities found.

Patched application dependencies were also verified inside Docker.

GitHub Actions has been configured to check dependency compatibility and scan dependencies before linting and regression testing.
### Docker Dependency Security

The initial Docker dependency audit identified vulnerabilities
in pip 25.0.1.

The Dockerfile was updated to install pip 26.2 before installing
application dependencies.

All application images were rebuilt.

Final Docker verification:
- Dependency compatibility: passed.
- Installed Python dependency vulnerability audit: passed.
- Application readiness: passed.

## 12. Regression Testing

| Test category | New tests |
|---|---:|
| Mass assignment and privilege escalation | 31 |
| BOLA | 15 |
| Administrator authorization | 30 |
| Sensitive response fields | 6 |
| Authentication hardening | 3 |
| Refresh rate limiting | 3 |
| Category validation | 3 |
| CORS | 9 |
| Security headers | 10 |
| Total | 110 |

Previous regression baseline: 298 tests.

Current regression baseline: 408 passing tests.

## 13. Remaining Security Considerations

The following require further production-hardening work:

- Production HTTPS and trusted reverse-proxy configuration.
- Content Security Policy compatible with API documentation.
- Distributed and account-based abuse prevention.
- Global request-size limits.
- Login and password-change concurrency review.
- Restricted external access to infrastructure endpoints.
- Comprehensive container and operating-system vulnerability scanning.
- Periodic credential rotation.
- External penetration testing and continuous monitoring.

Passing automated tests and vulnerability scans does not guarantee that the application is free of security vulnerabilities.

## 14. Conclusion

Module 14 implements application-level security hardening for the Helpdesk API, covering authorization, authentication, mass assignment, sensitive response fields, rate limiting, CORS, security headers and dependency management.

The implementation preserves existing business functionality while adding 110 security-focused regression tests.

Final acceptance requires successful remaining security checks, CI execution and mentor review.