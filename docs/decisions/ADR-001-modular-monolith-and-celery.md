# ADR-001: Modular Monolith with Independent Background Workers

## Status
Accepted

## Date
2026-11-13

## Context
The platform requires handling contest management, online IDE, code judging, real-time leaderboards, and hybrid proctoring for up to 500 concurrent participants. We evaluated architectural topologies:
1. **Full Microservices**: Separate microservices for Auth, Contests, Submissions, Judging, Scoring, and Proctoring.
2. **Standard Monolith**: All processes (API, judging, scheduler, proctoring) running in a single monolithic process.
3. **Modular Monolith + Independent Background Workers**: Unified domain business logic in FastAPI with dedicated, independently deployable background workers (Celery) and queue layers (Redis).

## Decision
Adopt a **Modular Monolith** architecture for the API backend paired with **independent Celery background workers** and **Redis**.

- **Backend API**: A single Python FastAPI codebase structured into distinct domain modules (`auth`, `contests`, `problems`, `submissions`, `judging`, `scoring`, `proctoring`, `websocket`).
- **Worker Tier**: Dedicated worker instances for Judge dispatch, Proctoring aggregation, Notifications, and Outbox Reconciliation.
- **Data Tier**: A single PostgreSQL primary database acting as the single source of truth, complemented by Redis for caching and Celery brokering.

## Alternatives Considered

### Full Microservices
- *Pros*: Independent deployment cycles, per-service technology specialization.
- *Cons*: High operational complexity, distributed transaction management (Saga/2PC), network latency overhead across RPCs, excessive operational burden for a 500-user target scale.
- *Rejected*: Premature distributed complexity violates our requirement for transactional data integrity and rapid development.

### Monolithic Single Process
- *Pros*: Simplest deployment.
- *Cons*: Heavy compilation/judging polling or screenshot processing would block web API event loops; worker crashes would kill the API server.
- *Rejected*: Fails non-functional requirements for reliability and fault isolation.

## Consequences
- Single codebase simplifies refactoring, shared types, and end-to-end integration testing.
- Background workers scale horizontally and independently based on workload (e.g. scaling judge workers during submission bursts without touching the web tier).
- Strong domain module boundaries must be enforced to prevent spaghetti dependencies.
