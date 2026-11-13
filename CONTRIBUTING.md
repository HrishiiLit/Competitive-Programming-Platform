# Contributing to the Competitive Programming Platform

First off, thank you for taking the time to contribute! 🎉

This document sets out the guidelines for contributing to the **Competitive Programming Platform with Hybrid Proctoring**. Following these guidelines helps maintain code quality, security, and architectural consistency across the project.

---

## 1. Code of Conduct

By participating in this project, you agree to abide by our [Code of Conduct](CODE_OF_CONDUCT.md). Please report unacceptable behavior to `conduct@cpplatform.local`.

---

## 2. Non-Negotiable Implementation Constraints

Before writing code or opening a PR, ensure your implementation adheres strictly to our core constraints:

1. **Never execute participant code inside the FastAPI process**: Always route through sandboxed Judge0 workers.
2. **Never expose hidden test cases** through participant-facing REST or WebSocket payloads.
3. **Never trust frontend clocks** for contest timing or submission cutoffs.
4. **Never allow Redis to be the sole source of truth** for submissions; always commit to PostgreSQL and use the Transactional Outbox.
5. **Never score the same accepted submission twice** (enforce idempotency).
6. **Never treat Judge0 infrastructure failures as wrong answers** (mark as `SYSTEM_ERROR` and retry).
7. **Never automatically disqualify participants** using algorithmic suspicion scores.
8. **Never expose evidence** through public object-storage URLs (use short-lived presigned URLs).
9. **Never modify a problem version** used by an active or historical contest.

---

## 3. Branching & Git Conventions

### Branch Naming Conventions:
- Feature branches: `feat/short-description` (e.g., `feat/monaco-autosave`)
- Bug fixes: `fix/issue-description` (e.g., `fix/judge-callback-hmac`)
- Documentation: `docs/section-name` (e.g., `docs/api-websocket-contract`)
- Refactoring / Performance: `refactor/subsystem-name`

### Commit Message Standards (Conventional Commits):
Format: `<type>(<scope>): <subject>`

Types:
- `feat`: A new user-facing or API feature.
- `fix`: A bug fix.
- `docs`: Documentation changes only.
- `test`: Adding or updating test suites.
- `refactor`: Code refactoring without behavioral changes.
- `chore`: Build scripts, dependencies, or tool configurations.

Examples:
- `feat(submissions): implement idempotency key check on POST /submissions`
- `fix(judging): handle crlf normalization in output comparator`
- `docs(api): update websocket connection contract with ticket handshake`

---

## 4. Coding Standards

### Backend (Python / FastAPI):
- **Version**: Python 3.11+
- **Type Annotations**: Strict typing required on all function signatures (`typing`, `pydantic`).
- **Formatting & Linting**: Format code with **Black** (line length 100) and lint with **Ruff**.
- **Data Validation**: Use **Pydantic v2** models for all API inputs and outputs.
- **ORM & Database**: Use SQLAlchemy 2.0+ async syntax. Avoid raw unparameterized SQL strings.

### Frontend (Next.js / TypeScript):
- **Framework**: Next.js 14+ (App Router), React 18+.
- **Type Safety**: TypeScript strict mode enabled with zero implicit `any`.
- **Styling**: Tailwind CSS with consistent design system tokens.
- **State Management**: Zustand for client-side state, TanStack Query for server state.
- **Code Editor**: Monaco Editor wrapper with optimized lazy loading.

---

## 5. Testing & Quality Assurance

Every PR must pass automated CI checks before merge:
- **Unit Tests**:
  - Backend: `pytest tests/unit/` (target: >85% coverage on business logic).
  - Frontend: `npm run test` (Vitest / React Testing Library).
- **Integration Tests**:
  - Test database operations against real PostgreSQL in Docker.
  - Test outbox polling and mock Judge0 callback execution.
- **Lint & Type Check**:
  - Backend: `ruff check app/` and `mypy app/`
  - Frontend: `npm run lint` and `npm run typecheck`

---

## 6. Pull Request Checklist

When submitting a pull request, ensure:
- [ ] Code follows all architectural constraints and security invariants.
- [ ] Unit and integration tests cover added or modified logic.
- [ ] Relevant documentation in `docs/` is updated.
- [ ] Database migrations are created via Alembic if models were modified.
- [ ] No private keys, passwords, or `.env` files are committed.
- [ ] PR title follows Conventional Commits.
