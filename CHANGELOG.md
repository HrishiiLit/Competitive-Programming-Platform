# Changelog

All notable changes to the **Competitive Programming Platform with Hybrid Proctoring** will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

---

## [Unreleased]

### Planned for Phase 0 & Phase 1 Execution
- Initial FastAPI application bootstrap with modular domain architecture.
- Alembic database migration scripts for PostgreSQL 16 schema baseline.
- Celery worker orchestration with Redis task broker.
- Judge0 CE integration technical spike and 6,000-execution capacity benchmark.
- Next.js 14+ frontend initialization with Monaco Editor integration.

---

## [1.1.0] - 2026-11-13

### Baseline Specification Release (v1.1)
- **Architecture**: Established Modular Monolith pattern (FastAPI) paired with independent Celery workers and Redis broker.
- **Data Durability**: Introduced Transactional Outbox Pattern to guarantee zero lost submissions across network or queue interruptions.
- **Coordination**: Specified PostgreSQL advisory-lock-based Single-Leader Scheduler for idempotent contest lifecycle transitions (`SCHEDULED` -> `LIVE` -> `COMPLETED`).
- **Timing Model**: Finalized authoritative server-side fixed-window timing model with derived durations (`end_time - start_time`) and strict submission cutoff enforcement.
- **Code Execution**: Integrated Judge0 CE via decoupled `JudgeProvider` adapter with batch execution, normalized text comparator, and fallback polling.
- **Scoring**: Formalized ICPC all-or-nothing binary scoring formula with 20-minute wrong-attempt penalties and 4-tier deterministic tie-breaking.
- **Proctoring**: Designed privacy-first hybrid proctoring model combining client-side face presence sampling, 60-second periodic screen downscaling (640x360 JPEG <100KB), direct S3 presigned upload, and human-in-the-loop disciplinary review.
- **API Contract**: Standardized REST endpoints under `/api/v1` with cursor pagination, standard error envelope, idempotency headers, and WebSocket real-time broadcast contracts under `/api/v1/ws/contests/{id}`.
- **Security & Privacy**: Formulated STRIDE threat model, Argon2id password hashing, rotating refresh tokens in secure HttpOnly cookies, RBAC authorization matrix, and DPDP / GDPR 7-day screenshot retention schedule.

---

## [1.0.0] - 2026-10-15

### Initial Concept & Draft Architecture
- Initial draft of functional requirements for public competitive programming.
- Preliminary assessment of compiler sandboxing and browser-based proctoring.
- Outlined user roles: `SUPER_ADMIN`, `ADMIN`, `ORGANIZER`, `PROCTOR`, and `PARTICIPANT`.
