# Roadmap: Competitive Programming Platform with Hybrid Proctoring

## Overview

This roadmap defines the implementation path for a high-performance, fault-tolerant competitive programming platform designed for 500 concurrent participants with Judge0 code evaluation, ICPC scoring, and hybrid proctoring.

## Phases

- [ ] **Phase 1: Core Foundation, Persistence & Authentication Engine** - Establish PostgreSQL models, Alembic migrations, Argon2id security, JWT tokens, and RBAC authentication APIs.
- [ ] **Phase 2: Contest Lifecycle & Problem Versioning Engine** - Implement contest timing state machine, problem authoring with versioning, and testcase storage.
- [ ] **Phase 3: Submission Ingestion, Transactional Outbox & Judge0 Integration** - Build durable submission pipeline, Celery judging workers, and HMAC-verified Judge0 adapter.
- [ ] **Phase 4: Scoring Engine & Real-Time Leaderboards** - Implement ICPC score calculation, contest freeze mechanics, and Redis-backed WebSocket standings broadcasts.
- [ ] **Phase 5: Hybrid Proctoring Subsystem** - Ingest browser blur/switch telemetry, presigned S3 evidence upload pipeline, suspicion index scoring, and proctor review.
- [ ] **Phase 6: Next.js Frontend & Monaco IDE** - Build responsive user interface with Monaco editor, contest arena, and proctor dashboard.
- [ ] **Phase 7: Hardening, Benchmarking & Deployment Readiness** - Execute 500-user concurrency benchmarks, security audits, and production Docker orchestration.

---

## Phase Details

### Phase 1: Core Foundation, Persistence & Authentication Engine
**Goal**: Deliver a hardened FastAPI backend foundation, complete database models across all domains, Alembic migration framework, Argon2id password hashing, JWT access/refresh token rotation, and public authentication endpoints.
**Depends on**: Nothing (Initial phase)
**Requirements**: [AUTH-01, AUTH-02, AUTH-03, AUTH-04]
**Success Criteria**:
  1. Complete PostgreSQL schema models implemented in SQLAlchemy 2.0 covering Users, Contests, Problems, Submissions, Outbox, and Proctoring.
  2. Alembic migration environment initialized and generating valid migrations.
  3. User registration, login, token refresh, and logout endpoints functional with Argon2id hashing and HttpOnly cookie / Bearer token support.
  4. Role-based access control (RBAC) middleware verifying Participant, Organizer, Proctor, and Admin permissions.
  5. Automated pytest suite passing with high coverage for all authentication and security flows.
**Plans**: 1/1 plans executed

Plans:
- [x] 01-01: Backend Foundation, Database Engine, User/Role Models, Security, and Auth REST APIs.

### Phase 2: Contest Lifecycle & Problem Versioning Engine
**Goal**: Deliver contest management with authoritative scheduling and problem authoring with version immutability.
**Depends on**: Phase 1
**Requirements**: [CONTEST-01, CONTEST-02, CONTEST-03, PROBLEM-01, PROBLEM-02, PROBLEM-03]
**Success Criteria**:
  1. Organizers can create and configure contests with fixed start/end timestamps and freeze thresholds.
  2. Problems can be created with Markdown/LaTeX statements, time/memory limits, and test cases.
  3. Problem versions lock immutably once attached to an active or past contest.
**Plans**: 1 plan

### Phase 3: Submission Ingestion, Transactional Outbox & Judge0 Integration
**Goal**: Deliver zero-loss submission ingestion, transactional outbox event emission, and asynchronous Judge0 code evaluation via Celery.
**Depends on**: Phase 2
**Requirements**: [SUBMIT-01, SUBMIT-02, SUBMIT-03, JUDGE-01, JUDGE-02, JUDGE-03, JUDGE-04]
**Success Criteria**:
  1. Submissions are saved durably in PostgreSQL with an associated outbox record before background dispatch.
  2. Celery workers dispatch code runs to Judge0 and handle callbacks with HMAC-SHA256 verification.
  3. Bounded polling fallback recovers orphaned or delayed submissions.
**Plans**: 1 plan

### Phase 4: Scoring Engine & Real-Time Leaderboards
**Goal**: Deliver ICPC scoring, tie-breaking rules, scoreboard freeze logic, and WebSocket leaderboard broadcasts.
**Depends on**: Phase 3
**Requirements**: [SCORE-01, SCORE-02, SCORE-03]
**Success Criteria**:
  1. Accurate ICPC calculation (+20 min penalty for wrong attempts prior to AC).
  2. Scoreboard freezes at designated threshold while participants continue seeing their own submissions.
  3. WebSockets push live standings updates to connected clients.
**Plans**: 1 plan

### Phase 5: Hybrid Proctoring Subsystem
**Goal**: Ingest browser telemetry events and screenshot evidence, score anomalies, and provide proctor review.
**Depends on**: Phase 1, Phase 2
**Requirements**: [PROCTOR-01, PROCTOR-02, PROCTOR-03, PROCTOR-04]
**Success Criteria**:
  1. Browser focus loss, tab change, and fullscreen exit events are ingested and stored.
  2. Presigned S3 URLs allow secure upload of periodic webcam and screen captures.
  3. Proctor console displays flagged participants and evidence timeline.
**Plans**: 1 plan

### Phase 6: Next.js Frontend & Monaco IDE
**Goal**: Build a modern, accessible web interface for participants, organizers, and proctors.
**Depends on**: Phase 1, Phase 2, Phase 3, Phase 4, Phase 5
**Requirements**: [UI-01, UI-02, UI-03]
**Success Criteria**:
  1. Contest arena renders problems with KaTeX math and Monaco code editor.
  2. Real-time submission status and live scoreboard display seamlessly.
  3. Organizer and proctor consoles provide intuitive management interfaces.
**Plans**: 2 plans

### Phase 7: Hardening, Benchmarking & Deployment Readiness
**Goal**: Validate 500-participant load capacity, fault recovery, and production container orchestration.
**Depends on**: Phase 6
**Requirements**: All
**Success Criteria**:
  1. Load test demonstrates 25 sustained executions/sec and 50 burst executions/sec under representative load.
  2. Database point-in-time recovery and failover verified.
  3. Full Docker Compose stack starts cleanly and passes end-to-end health checks.
**Plans**: 1 plan
