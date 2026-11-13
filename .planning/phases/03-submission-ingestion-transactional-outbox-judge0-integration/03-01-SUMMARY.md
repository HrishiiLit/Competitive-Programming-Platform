---
phase: 03-submission-ingestion-transactional-outbox-judge0-integration
plan: 01
subsystem: judging-and-submissions
tags: [submissions, transactional-outbox, judge0, comparator, rate-limiting, hmac-callbacks]
dependency_graph:
  requires: [02-01]
  provides: [submission-ingestion, judge-execution, polling-recovery, verdict-aggregation]
  affects: [04-01, 05-01]
tech_stack:
  added: []
  patterns: [Transactional Outbox, Provider Adapter, HMAC SHA-256 Webhooks, Deterministic Output Normalization, Bounded Polling Fallback]
key_files:
  created:
    - backend/app/services/judging/comparator.py
    - backend/app/services/judging/provider.py
    - backend/app/services/judging/judge0.py
    - backend/app/services/submissions/service.py
    - backend/app/services/judging/service.py
    - backend/app/schemas/submission.py
    - backend/app/api/v1/submissions.py
    - backend/app/api/v1/internal.py
    - backend/tests/test_submissions_and_judging.py
  modified:
    - backend/app/models/submission.py
    - backend/app/models/problem.py
    - backend/app/api/v1/router.py
decisions:
  - "Decoupled judging execution behind JudgeProvider abstract interface with Judge0 CE concrete implementation."
  - "Enforced transactional outbox pattern writing Submission and OutboxEvent in single atomic DB transaction."
  - "Built deterministic output comparator handling CRLF, trailing line whitespace, and trailing empty lines without fuzzy tolerance."
  - "Implemented strict verdict priority matrix (SYSTEM_ERROR > COMPILATION_ERROR > First Failing Test (TLE > MLE > OLE > RE > WA) > ACCEPTED)."
  - "Added rate limit check enforcing max 1 submission every 5 seconds per problem per user with 429 Too Many Requests."
metrics:
  duration: 10m
  completed_date: "2026-11-14"
status: complete
actuals:
  tokens: 16250
  tasks: 5
  commits: 5
  plan_head_before: 4f86385ed26d7cbdf8e32137eb72c3a868d7c60a
  plan_head_after: 839b2b01e672c1befc8641ce9f1186e82da9dbf4
---

# Phase 03 Plan 01: Submission Ingestion, Transactional Outbox & Judge0 Integration Summary

Substantive delivery of durable submission ingestion, transactional outbox event publishing, Judge0 CE execution adapter with HMAC-SHA256 signature verification, bounded polling recovery, deterministic CRLF/whitespace comparator, and authoritative verdict priority aggregation engine.

## What Was Built

1. **Deterministic Output Normalizer & Comparator (`backend/app/services/judging/comparator.py`)**:
   - Normalizes Windows CRLF (`\r\n`) and legacy CR (`\r`) to standard Unix LF (`\n`).
   - Strips trailing whitespace from every individual output line while preserving leading indentation and internal whitespace.
   - Strips trailing blank lines at the conclusion of stdout.
   - Deterministically compares actual stdout against expected test case output.

2. **JudgeProvider Abstraction & Judge0 Concrete Adapter (`backend/app/services/judging/provider.py`, `judge0.py`)**:
   - `JudgeProvider`: Abstract interface specifying batch dispatch (`create_batch`), single status polling (`get_submission`), batch polling (`get_submissions_batch`), and HMAC signature verification (`verify_callback_signature`).
   - `Judge0Provider`: Concrete implementation with base64 payload encoding/decoding, HMAC-SHA256 callback signing and verification, and status ID mapping (`3 -> AC`, `4 -> WA`, `5 -> TLE`, `6 -> CE`, `7..12 -> RE`, `13..14 -> IE`).
   - Domain verdict priority constants defined: `SYSTEM_ERROR (IE) > COMPILATION_ERROR (CE) > First Failing Test (TLE > MLE > OLE > RE > WA) > ACCEPTED (AC)`.

3. **Submission Ingestion & Transactional Outbox (`backend/app/services/submissions/service.py`)**:
   - Rate limiting: Prevents rapid-fire resubmission by enforcing a 5-second cooldown per problem per user, returning `429 Too Many Requests`.
   - Contest state gating: Rejects submissions when a contest is `UPCOMING`, `COMPLETED`, or `DRAFT`. Ensures only registered and approved participants can submit during `ACTIVE` or `FROZEN` windows.
   - Atomicity: Submissions and `OutboxEvent` records (`event_type="submission.created"`) are written in a single database transaction.

4. **Judging Lifecycle, HMAC Webhook Processor & Polling Fallback (`backend/app/services/judging/service.py`)**:
   - Batch testcase dispatch: Creates `SubmissionRun` records linked to Judge0 tokens and marks submission `RUNNING`.
   - HMAC callback ingestion: Verifies incoming SHA-256 signatures, updates `SubmissionRun` execution time/memory/verdict, and audits webhook payloads in `Judge0Callback`.
   - Automatic aggregation: When all runs complete, applies the priority matrix to calculate final submission verdict, max time, max memory, and first failing test case number.
   - Bounded polling fallback: Periodically or on-demand polls Judge0 for incomplete test runs to recover from lost or delayed webhook deliveries.

5. **REST Endpoints & Webhooks (`backend/app/api/v1/submissions.py`, `internal.py`)**:
   - `POST /api/v1/submissions`: Participant code submission with validation and outbox generation.
   - `GET /api/v1/submissions`: List submissions with filtering; participants are restricted to viewing their own submissions while staff can view all.
   - `GET /api/v1/submissions/{id}`: Detailed submission inspection with confidentiality guards hiding source code and non-sample test details from unauthorized participants.
   - `POST /api/v1/internal/judge-callbacks`: Webhook receiver requiring valid HMAC signature headers.

6. **Automated Test Suite (`backend/tests/test_submissions_and_judging.py`)**:
   - 9 comprehensive test scenarios verifying comparator edge cases, verdict priority precedence, outbox transaction atomicity, 5-second rate limiting, contest window rejection, mocked Judge0 batch flow, polling recovery, and REST endpoints.
   - 100% test pass rate across all 25 tests in the platform suite.

## Verification & Test Results

```
============================= test session starts =============================
platform win32 -- Python 3.14.3, pytest-9.0.3, pluggy-1.6.0
collected 9 items

tests/test_submissions_and_judging.py::test_output_comparator_crlf_and_whitespace PASSED [ 11%]
tests/test_submissions_and_judging.py::test_verdict_priority_indices PASSED [ 22%]
tests/test_submissions_and_judging.py::test_verdict_aggregation_priority PASSED [ 33%]
tests/test_submissions_and_judging.py::test_submission_ingestion_and_outbox_atomicity PASSED [ 44%]
tests/test_submissions_and_judging.py::test_submission_rate_limiting PASSED [ 55%]
tests/test_submissions_and_judging.py::test_contest_submission_window_and_registration PASSED [ 66%]
tests/test_submissions_and_judging.py::test_judging_dispatch_callback_and_polling PASSED [ 77%]
tests/test_submissions_and_judging.py::test_submission_api_endpoints PASSED [ 88%]
tests/test_submissions_and_judging.py::test_judge0_webhook_endpoint PASSED [100%]

============================== 9 passed in 5.45s ==============================
```

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] SQLAlchemy lazy loading missing greenlet prevention**
- **Found during:** Task 2 implementation
- **Issue:** Accessing `submission.runs`, `submission.problem`, `submission.language`, and `run.test_case` in async queries can raise `MissingGreenlet` in SQLite/asyncpg if default lazy loading is retained.
- **Fix:** Added `lazy="selectin"` to relationship configurations in `backend/app/models/submission.py`.
- **Files modified:** `backend/app/models/submission.py`
- **Commit:** `5d030e4`

**2. [Rule 1 - Bug] Pytest collection warning for TestCase database model**
- **Found during:** Task 5 test execution
- **Issue:** Pytest automatically attempts to discover test cases on any class whose name starts with `Test`, producing a `PytestCollectionWarning` on `app.models.problem.TestCase`.
- **Fix:** Added `__test__ = False` attribute to `TestCase` model in `backend/app/models/problem.py`.
- **Files modified:** `backend/app/models/problem.py`
- **Commit:** `839b2b0`

## Known Stubs
None - all submission ingestion, outbox persistence, comparator, provider, callback processing, and polling mechanisms are fully implemented and verified against the database and mock judge services.

## Threat Flags
None. All webhook endpoints require HMAC-SHA256 authentication against shared secrets, participant submissions enforce rate limiting and contest access controls, and hidden test inputs/outputs are never leaked to participants.

## Self-Check: PASSED
- [x] `backend/app/services/judging/comparator.py` exists
- [x] `backend/app/services/judging/provider.py` exists
- [x] `backend/app/services/judging/judge0.py` exists
- [x] `backend/app/services/submissions/service.py` exists
- [x] `backend/app/services/judging/service.py` exists
- [x] `backend/app/schemas/submission.py` exists
- [x] `backend/app/api/v1/submissions.py` exists
- [x] `backend/app/api/v1/internal.py` exists
- [x] `backend/tests/test_submissions_and_judging.py` exists
- [x] Commits `970ef17`, `5d030e4`, `302f7ae`, `bfc2d56`, `839b2b0` verified in git history
