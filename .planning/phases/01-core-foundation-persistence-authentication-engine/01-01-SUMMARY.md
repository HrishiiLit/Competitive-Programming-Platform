---
phase: 01-core-foundation-persistence-authentication-engine
plan: 01
subsystem: backend-auth-persistence
tags: [fastapi, sqlalchemy, alembic, argon2id, jwt, rbac, pytest]
status: complete
requires: []
provides: [database-models, auth-service, jwt-tokens, rbac-middleware]
affects: [all-subsystems]
tech-stack:
  added: [fastapi, sqlalchemy, asyncpg, aiosqlite, alembic, argon2-cffi, pyjwt, pydantic, email-validator, pytest, pytest-asyncio]
  patterns: [modular-monolith, async-session-per-request, selectinload-eager-relationships, refresh-token-rotation-replay-detection]
key-files:
  created:
    - backend/app/models/contest.py
    - backend/app/models/problem.py
    - backend/app/models/submission.py
    - backend/app/models/standing.py
    - backend/app/models/proctoring.py
    - backend/app/models/audit.py
    - backend/app/models/__init__.py
    - backend/alembic.ini
    - backend/migrations/env.py
    - backend/migrations/script.py.mako
    - backend/app/services/auth/service.py
    - backend/app/api/deps.py
    - backend/app/schemas/auth.py
    - backend/app/api/v1/auth.py
    - backend/app/api/v1/router.py
    - backend/app/main.py
    - backend/tests/conftest.py
    - backend/tests/test_auth.py
  modified:
    - backend/app/core/config.py
    - backend/app/core/database.py
    - backend/app/core/security.py
    - backend/app/models/user.py
decisions:
  - "Decided to configure lazy='selectin' on User.user_roles and UserRole.role to avoid async MissingGreenlet exceptions during relationship access."
  - "Decided to normalize SQLite naive datetimes with timezone.utc during token expiry comparisons to ensure universal database compatibility."
metrics:
  duration: 15 min
  completed_date: "2026-11-13"
actuals:
  tokens: 42000
  tasks: 5
  commits: 5
  plan_head_before: 539e5d5b3d536ed4a771bbf2fe818733da9e575e
  plan_head_after: 335e34f1625f935d98666ff6c1e45aa1c6e7d69a
---

# Phase 01 Plan 01: Core Foundation, Persistence & Authentication Engine Summary

Hardened FastAPI backend foundation with 28 relational domain models in SQLAlchemy 2.0, Alembic async migrations, Argon2id password hashing, JWT token rotation with replay detection, role-based access control, and an automated pytest test suite.

## What Was Delivered

1. **Complete Database Schema Models (28 Tables)**:
   - Identity & Auth: `User`, `Role`, `UserRole`, `RefreshToken`, `EmailVerificationToken`, `PasswordResetToken`, `Language`.
   - Contests: `Contest`, `ContestProblem`, `ContestRegistration`.
   - Problems: `Problem`, `ProblemVersion`, `TestCase`.
   - Submissions & Outbox: `Submission`, `SubmissionRun`, `OutboxEvent`, `Judge0Callback`.
   - Standings & Drafts: `CodeDraft`, `ContestStanding`, `StandingProblemResult`.
   - Proctoring: `ProctoringSession`, `ProctoringEvent`, `ProctoringEvidence`, `DisciplinaryAction`, `ContestAppeal`.
   - Communication & Audit: `ClarificationRequest`, `ContestAnnouncement`, `AuditLog`.

2. **Alembic Database Migration Configuration**:
   - `alembic.ini` and `migrations/env.py` configured with asyncpg and dynamic application settings discovery.
   - Verified that Alembic targets all 28 tables.

3. **Cryptographic Security & Authentication Engine**:
   - Argon2id password hashing with hardened parameters (time_cost=3, memory_cost=65536, parallelism=4).
   - JWT access token generation (15 min) and SHA-256 hashed refresh token generation (7 days).
   - Refresh token rotation with automatic replay attack revocation (revoking all user sessions upon reuse of expired/revoked token).
   - Single-use cryptographic token lifecycle for email verification and password resets.

4. **FastAPI REST Endpoints & RBAC Middleware**:
   - `POST /api/v1/auth/register`: registers participant with validation and default `PARTICIPANT` role.
   - `POST /api/v1/auth/login`: validates credentials, issues access/refresh tokens and optional HttpOnly cookies.
   - `POST /api/v1/auth/refresh`: rotates refresh token and provides new access token.
   - `POST /api/v1/auth/logout`: revokes active refresh tokens.
   - `GET /api/v1/auth/me`: protected profile endpoint resolving current authenticated user and roles.
   - Dependencies `get_db`, `get_current_user`, and `require_roles`.

5. **Automated Pytest Suite**:
   - In-memory SQLite async test fixtures in `backend/tests/conftest.py`.
   - 10 automated test cases in `backend/tests/test_auth.py` verifying registration, duplicate rejection, input validation, login, rotation, replay defense, profile resolution, and logout.
   - 100% test pass rate in 5.83s.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Added explicit `lazy='selectin'` to User and UserRole relationships**
- **Found during:** Task 5 test execution
- **Issue:** Accessing `user.user_roles` raised `sqlalchemy.exc.MissingGreenlet` due to implicit synchronous lazy loading on async session.
- **Fix:** Added `lazy="selectin"` to `User.user_roles` and `UserRole.role`, ensuring relationships are eagerly loaded asynchronously.
- **Files modified:** `backend/app/models/user.py`, `backend/app/services/auth/service.py`
- **Commit:** `335e34f`

**2. [Rule 1 - Bug] Normalized offset-naive datetimes in SQLite for token expiry comparisons**
- **Found during:** Task 5 test execution
- **Issue:** SQLite returns offset-naive datetimes for `expires_at`, causing `TypeError: can't compare offset-naive and offset-aware datetimes` against `utc_now()`.
- **Fix:** Checked `expires_at.tzinfo is None` and attached `timezone.utc` before comparison.
- **Files modified:** `backend/app/services/auth/service.py`
- **Commit:** `335e34f`

**3. [Rule 3 - Blocker] Installed required Python dependencies**
- **Found during:** Task 1, 4, 5
- **Issue:** Missing `sqlalchemy[asyncio]`, `asyncpg`, `aiosqlite`, `argon2-cffi`, `alembic`, `email-validator`, and `pytest-asyncio`.
- **Fix:** Installed dependencies matching `backend/requirements.txt`.
- **Files modified:** `backend/requirements.txt`

## Verification

- `python -c "from app.models import Base; print(len(Base.metadata.tables))"` -> 28 tables.
- `python -c "from migrations.env import target_metadata; print(len(target_metadata.tables))"` -> 28 tables.
- `pytest backend/tests/ -v` -> 10 passed in 5.83s.

## Self-Check: PASSED
- [x] All 5 tasks completed and verified
- [x] 5 task commits present in git history
- [x] All tests passing cleanly
- [x] All 28 domain models active
