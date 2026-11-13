# ADR-003: Judge0 CE Integration and Transactional Outbox Pattern

## Status
Accepted

## Date
2026-11-13

## Context
The platform needs to evaluate code submissions in C++, Python, and Java while sustaining 25–50 test executions per second. Key challenges:
1. Writing a custom compiler sandbox and process isolation engine requires immense security engineering.
2. Direct asynchronous task publishing during HTTP requests risks lost submissions if Redis crashes between the DB commit and queue push (dual-write problem).

## Decision
1. **Integrate Judge0 Community Edition (CE)** via a decoupled `JudgeProvider` adapter interface.
2. **Implement the Transactional Outbox Pattern** in PostgreSQL to guarantee zero lost submissions.

- Submissions and outbox records (`transactional_outbox`) are committed in a single atomic database transaction.
- An independent dispatcher polls the outbox and publishes jobs to Celery.
- A reconciler process detects and re-enqueues orphaned or stuck submissions.
- Judge0 infrastructure failures yield `SYSTEM_ERROR` and automatic retry; they are NEVER evaluated as `WRONG_ANSWER`.

## Alternatives Considered

### In-House Custom Sandboxing (nsjail / Docker API)
- *Pros*: Custom tailored performance.
- *Cons*: High security risk, high development overhead, delays delivery of core platform capabilities.
- *Rejected*: Out of scope for V1.

### Direct Celery Publishing (No Outbox)
- *Pros*: Marginally lower latency by skipping outbox table.
- *Cons*: If Redis experiences a network partition or failover during the request, the database holds a submission record that is never executed.
- *Rejected*: Violates our requirement that accepted submissions must never be lost.

## Consequences
- Guaranteed at-least-once delivery of judging jobs.
- Clear separation between application business logic and execution sandbox.
- Mandatory Phase 0 capacity spike to validate that Judge0 meets the 6,000-execution benchmark under multi-language loads.
