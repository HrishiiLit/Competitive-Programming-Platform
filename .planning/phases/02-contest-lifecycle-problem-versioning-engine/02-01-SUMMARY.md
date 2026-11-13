---
phase: 02-contest-lifecycle-problem-versioning-engine
plan: 01
subsystem: contest-problems
tags: [fastapi, sqlalchemy, contest-lifecycle, problem-versioning, immutability, testcases, pytest]
status: complete
requires: [01-01]
provides: [contest-service, problem-service, contest-endpoints, problem-endpoints]
affects: [submission-engine, scoring-engine, judging-engine]
tech-stack:
  added: [pytest-asyncio]
  patterns: [fixed-window-timing, version-immutability-locking, sample-hidden-testcase-segregation, authoritative-clock-sync]
key-files:
  created:
    - backend/app/schemas/problem.py
    - backend/app/schemas/contest.py
    - backend/app/services/problems/service.py
    - backend/app/services/contests/service.py
    - backend/app/api/v1/problems.py
    - backend/app/api/v1/contests.py
    - backend/tests/test_contests_and_problems.py
  modified:
    - backend/app/models/contest.py
    - backend/app/models/problem.py
    - backend/app/api/v1/router.py
decisions:
  - "Decided to strictly enforce problem version immutability by rejecting edits (HTTP 409 Conflict) once a problem is bound to an active or past contest."
  - "Decided to enforce server-authoritative fixed-window timing where problems in upcoming contests are strictly confidential (HTTP 403 Forbidden) to participants until the start_time arrives."
  - "Decided to segregate testcase queries so that participants can only ever inspect sample testcases (is_sample=True), preserving hidden testcase confidentiality."
metrics:
  duration: 12 min
  completed_date: "2026-11-13"
actuals:
  tokens: 38000
  tasks: 5
  commits: 5
  plan_head_before: abd31fffa9ce04d671706b9ebef15a533264818b
  plan_head_after: d76c74da40df590a4cec12453ade943b65c6af4b
---

# Phase 02 Plan 01: Contest Lifecycle & Problem Versioning Engine Summary

Comprehensive implementation of contest scheduling, server-authoritative status state machine, problem authoring with versioning and immutability locking, testcase confidentiality segregation, and participant registration.

## What Was Delivered

1. **Problem Management, Versioning & Testcases Service**:
   - `create_problem`: creates a new problem with initial version 1, time/memory limits, and Markdown/LaTeX statement specifications.
   - `create_new_version`: creates sequential versions of problems with optional testcase inheritance.
   - `assert_version_mutable`: checks whether a problem version is bound to an active or concluded contest (`ACTIVE`, `FROZEN`, `COMPLETED`, `FINALIZED`). Raises 409 Conflict if mutation is attempted on a locked version.
   - `add_test_case` & `get_test_cases`: manages public sample test cases (`is_sample=True`) and hidden evaluation test cases (`is_sample=False`). Enforces that participants are never exposed to hidden test cases.

2. **Contest Lifecycle & Authoritative State Machine**:
   - `calculate_contest_status`: evaluates dynamic contest state (`DRAFT` -> `UPCOMING` -> `ACTIVE` -> `FROZEN` -> `COMPLETED` -> `FINALIZED`) strictly according to server UTC time.
   - Fixed-window timing validation: ensures `start_time < end_time` and `start_time < freeze_time <= end_time`.
   - `add_problem_to_contest`: assigns problems to contests with unique order letters (`A`, `B`, `C`...) and point values.
   - `register_participant`: provides idempotent participant registration before contest conclusion.
   - `can_view_problems`: ensures problems in upcoming contests remain confidential until the contest start timestamp arrives.

3. **Pydantic Schemas & Data Serialization**:
   - `backend/app/schemas/problem.py`: schemas for problem creation, versioning, and testcase management.
   - `backend/app/schemas/contest.py`: schemas for contest creation, updating, problem assignment, registration, and server time synchronization (`ServerTimeResponse`).

4. **FastAPI REST Endpoints**:
   - `GET /api/v1/contests/time`: authoritative server time endpoint.
   - `POST /api/v1/contests`: contest authoring (Organizer/Admin).
   - `GET /api/v1/contests`: contest discovery with dynamic status resolution.
   - `GET /api/v1/contests/{id_or_slug}`: contest details and participant registration status.
   - `POST /api/v1/contests/{id}/register`: participant registration.
   - `POST /api/v1/contests/{id}/problems`: problem assignment with order letters.
   - `GET /api/v1/contests/{id}/problems`: contest problem listing (gated by active status or staff role).
   - `POST /api/v1/problems`: problem creation (Organizer/Admin).
   - `GET /api/v1/problems`: problem catalog.
   - `GET /api/v1/problems/{id}`: problem details with current version.
   - `POST /api/v1/problems/{id}/versions`: problem version creation.
   - `POST /api/v1/problems/{id}/versions/{version_id}/testcases`: testcase upload.
   - `GET /api/v1/problems/{id}/versions/{version_id}/testcases`: testcase retrieval filtered by caller role.

5. **Automated Pytest Suite**:
   - 6 new automated test cases in `backend/tests/test_contests_and_problems.py`.
   - Full test suite: 16 passed in 9.99s with 100% success.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Used `@pytest_asyncio.fixture` for async test fixtures**
- **Found during:** Task 5 test execution
- **Issue:** `pytest-asyncio` in strict mode raised `PytestRemovedIn9Warning` when using plain `@pytest.fixture` with an async generator.
- **Fix:** Used `@pytest_asyncio.fixture` for `organizer_token` and `participant_token`.
- **Files modified:** `backend/tests/test_contests_and_problems.py`
- **Commit:** `d76c74d`

## Verification

- `pytest backend/tests/test_contests_and_problems.py -v` -> 6 passed.
- `pytest backend/tests/ -v` -> 16 passed.

## Self-Check: PASSED
- [x] All 5 tasks completed and verified
- [x] 5 task commits present in git history
- [x] All 16 automated tests passing cleanly
- [x] Immutability locking and testcase confidentiality verified
