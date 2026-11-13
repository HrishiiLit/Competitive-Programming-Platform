# Requirements: Competitive Programming Platform with Hybrid Proctoring

## Identity & Access Control (AUTH)

- [ ] **AUTH-01**: User registration with username uniqueness, email validation, and Argon2id password hashing.
- [ ] **AUTH-02**: JWT-based access token issuance (15-min) and secure database-backed refresh token rotation (7-day, SHA-256 hashed).
- [ ] **AUTH-03**: Role-based access control (RBAC) enforcing Participant, Organizer, Proctor, and Administrator capabilities.
- [ ] **AUTH-04**: Cryptographic single-use token issuance for email verification and password reset workflows.

## Contest Lifecycle & Participation (CONTEST)

- [ ] **CONTEST-01**: Contest authoring with fixed-window start/end timing, scoreboard freeze threshold, and unfreeze scheduling.
- [ ] **CONTEST-02**: Participant contest registration, eligibility enforcement, and server-authoritative timer synchronization.
- [ ] **CONTEST-03**: Server-side contest status state machine (`DRAFT`, `UPCOMING`, `ACTIVE`, `FROZEN`, `COMPLETED`, `FINALIZED`).

## Problem Management & Testcases (PROBLEM)

- [ ] **PROBLEM-01**: Versioned problem authoring with Markdown/LaTeX statements, time/memory limits, and language permissions.
- [ ] **PROBLEM-02**: Problem immutability enforcement when bound to an active or concluded contest.
- [ ] **PROBLEM-03**: Test case management separating public sample test cases from encrypted/hidden evaluation suites.

## Submission & Outbox Delivery (SUBMIT)

- [ ] **SUBMIT-01**: Durable submission ingestion persisting directly to PostgreSQL before queue publication.
- [ ] **SUBMIT-02**: Transactional outbox event creation ensuring zero submission loss under message broker transient failures.
- [ ] **SUBMIT-03**: Submission rate limiting per user per problem (e.g., max 1 submission every 5 seconds).

## Judging Engine & Judge0 Integration (JUDGE)

- [ ] **JUDGE-01**: Celery worker consuming outbox events and dispatching code runs to Judge0 CE.
- [ ] **JUDGE-02**: Judge0 callback validation using HMAC-SHA256 signature verification.
- [ ] **JUDGE-03**: Bounded polling fallback for Judge0 results when webhook callbacks are delayed or lost.
- [ ] **JUDGE-04**: Test execution result mapping (`AC`, `WA`, `TLE`, `MLE`, `RE`, `CE`, `IE`).

## Scoring & Real-Time Leaderboards (SCORE)

- [ ] **SCORE-01**: ICPC binary scoring calculation (count of solved problems, total penalty minutes, 20-min incorrect attempt penalty).
- [ ] **SCORE-02**: Scoreboard freeze behavior concealing post-freeze verdict changes from public viewers.
- [ ] **SCORE-03**: WebSocket live standings broadcasting with Redis Pub/Sub backend.

## Hybrid Proctoring & Evidence Ingestion (PROCTOR)

- [ ] **PROCTOR-01**: Telemetry ingestion for browser window blur, tab switching, and fullscreen departures.
- [ ] **PROCTOR-02**: Secure presigned S3 URL generation for periodic client webcam and screen evidence uploads.
- [ ] **PROCTOR-03**: Server-side anomaly detection and suspicion index calculation.
- [ ] **PROCTOR-04**: Proctor review console for flagged event inspection, timeline playback, and disciplinary logging.

## Frontend Experience (UI)

- [ ] **UI-01**: Responsive Next.js application with dark-mode aesthetic and accessibility compliance.
- [ ] **UI-02**: Monaco-powered online IDE with syntax highlighting, language selector, and test runner interface.
- [ ] **UI-03**: Live contest arena with synchronized countdown clock, problem statements, and real-time submission feed.
