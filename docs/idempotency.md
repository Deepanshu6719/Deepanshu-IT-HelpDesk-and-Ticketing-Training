# Idempotency Strategy

## 1. Problem Statement

The ticket creation endpoint (`POST /api/v1/tickets`) is currently non-idempotent.

When a client submits the same request multiple times, each successful request creates a new ticket. This can result in duplicate tickets and duplicate notification tasks when clients retry requests following network failures or response timeouts.

## 2. Demonstrated Behaviour

The automated demonstration in `tests/test_idempotency.py` verifies the following:

- Two identical POST requests return HTTP 201.
- The first request creates ticket ID 1.
- The second request creates ticket ID 2.
- The database contains two matching ticket records.

This confirms that duplicate creation is possible.

## 3. Proposed Solution

Introduce an optional `Idempotency-Key` HTTP request header for ticket creation.

The client generates a unique key, preferably a UUID, for each intended ticket creation operation and reuses that key when retrying the operation.

The server authenticates the client before processing the idempotency key.

## 4. Expected Behaviour

| Request scenario | Expected result |
|---|---|
| New key | Create ticket and store response |
| Same key and same payload | Replay original response |
| Same key and different payload | Return HTTP 409 Conflict |
| Different key and same payload | Create a separate ticket |
| Same key used by different users | Treat as independent operations |
| No key provided | Continue normal POST behaviour |
| Concurrent requests with the same key | Create at most one ticket |

## 5. Storage Strategy

Use a PostgreSQL table named `idempotency_keys`.

Proposed fields:

| Field | Purpose |
|---|---|
| id | Primary key |
| user_id | Authenticated user |
| operation | Versioned endpoint and HTTP method |
| idempotency_key | Client-generated identifier |
| request_hash | SHA-256 hash of normalized request payload |
| response_body | Original successful response stored as JSONB |
| status_code | Original HTTP status code |
| created_at | Record creation timestamp |
| expires_at | Record expiration timestamp |

Apply a unique constraint on `(user_id, operation, idempotency_key)`.

This prevents different users or API operations from interfering with one another.

## 6. Request Processing

1. Authenticate the user and validate the request.
2. Read and validate the Idempotency-Key header.
3. Generate a deterministic hash of the validated request payload.
4. Begin a database transaction.
5. Atomically attempt to reserve the idempotency key.
6. If the key already exists, compare request hashes.
7. Return HTTP 409 if the hashes differ.
8. Replay the stored response if the hashes match and the operation is complete.
9. Otherwise, create the ticket and store its successful response.
10. Commit the transaction.

A replay must not create another ticket or publish another notification task.

## 7. Concurrency and Atomicity

The database unique constraint prevents two concurrent transactions from independently reserving the same key.

Ticket creation and idempotency response storage must occur within the same database transaction.

If the transaction fails, both operations must roll back.

The implementation must safely handle uniqueness conflicts, transaction failures and concurrent requests.

## 8. Notification Side Effects

Notification tasks should not be published again when replaying an existing response.

For stronger reliability, a future implementation should introduce the transactional outbox pattern. Notification events would be stored in PostgreSQL within the ticket creation transaction and published separately by an outbox processor.

Notification consumers should also support deduplication because task delivery may occur more than once.

## 9. Expiration Policy

Retain completed idempotency records for 24 hours.

Expired records can be removed through a periodic cleanup task.

Clients must understand that retrying an operation after its idempotency record has expired may create another ticket.

## 10. Security Considerations

- Scope idempotency keys to authenticated users and API operations.
- Validate key length and format.
- Never use an idempotency key as an authentication credential.
- Do not store access tokens, passwords or other authentication secrets.
- Apply appropriate rate limits.
- Generate a new request ID for every HTTP request, including replayed requests.

## 11. Implementation Status

The duplicate POST behaviour has been demonstrated through automated testing.

The proposed idempotency mechanism is documented but has not yet been implemented.

Full implementation is deferred to a future enhancement.