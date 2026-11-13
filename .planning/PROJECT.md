# Competitive Programming Platform with Hybrid Proctoring

## What This Is

A production-grade, public competitive programming platform enabling organizers to create and host algorithmic contests, and participants to register, solve problems, submit solutions, and view live ICPC-style leaderboards through a browser-based interface. The platform features an integrated code editor (Monaco), automated code evaluation via Judge0 CE, and a non-invasive hybrid proctoring subsystem (monitoring tab focus, multi-face presence, and periodic webcam/screen snapshots).

## Core Value

The primary engineering priority is the absolute correctness, durability, and reliability of the contest lifecycle and judging engine. Proctoring is an independent integrity layer that never interferes with, blocks, or halts code execution and contest scoring.

## Technical Architecture

- **Backend**: FastAPI modular monolith with asynchronous SQLAlchemy 2.0 and Pydantic v2.
- **Workers**: Celery workers backed by Redis for judge submission queueing, proctoring evidence processing, and outbox event dispatching.
- **Database**: PostgreSQL 16 as the single source of truth; transactional outbox pattern guarantees durable event emission.
- **Judge Engine**: Judge0 CE sandboxed code execution adapter with HMAC-signed callbacks and bounded polling fallback.
- **Frontend**: Next.js (App Router, React 19) with Tailwind CSS, shadcn/ui, and Monaco Editor.
- **Storage**: S3-compatible private object storage (MinIO / Cloudflare R2 / AWS S3) for proctoring screenshots and hidden testcases via short-lived presigned URLs.
- **Real-time Hub**: WebSockets for contest timers, submission judge verdicts, and live scoreboard updates.

## Key Requirements & Invariants

1. **Isolation**: Never execute untrusted participant code directly inside the API process.
2. **Confidentiality**: Never expose hidden test cases, expected outputs, or comparator checkers to participants.
3. **Authoritative Clock**: Contest start, end, and duration must be validated strictly on the server against PostgreSQL/Redis; client clocks are never trusted.
4. **Idempotent Scoring**: Accepted submissions cannot be scored more than once, and penalties follow strict ICPC rules (+20 min per incorrect attempt prior to AC).
5. **Durable Submissions**: Submissions are durably stored in PostgreSQL before being queued to Redis; Redis crashes cannot lose accepted submissions.
6. **Proctoring Independence**: Proctoring score calculations and screenshot collection run asynchronously without impeding contest timing or code submission paths.

## Constraints

- Target Scale: 500 concurrent participants, 200-submission bursts.
- Submissions burst processing: 25 completed test executions/sec sustained, 50/sec burst.
- Database recovery: RPO <= 5 min with PITR, RTO <= 60 min.
