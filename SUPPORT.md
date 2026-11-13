# Support Policy & Guidelines

Thank you for using and contributing to the **Competitive Programming Platform with Hybrid Proctoring**. This document outlines how to get help, report issues, and understand our support scope.

---

## 1. Where to Seek Help

| Channel | Purpose | Expected Response |
|---|---|---|
| **[Documentation](docs/)** | Architecture, API specs, database schema, judging, and proctoring guides | Instant self-service |
| **GitHub Discussions** | General questions, architecture ideas, setup assistance | Community / Maintainers |
| **GitHub Issues** | Reproducible bug reports and verified feature requests | Triaged by severity (see below) |
| **Security Email** | Vulnerability disclosures (`security@cpplatform.local`) | 24–48 hours (see [SECURITY.md](SECURITY.md)) |

---

## 2. Supported Scope

### What We Support:
- Core platform installation and Docker Compose setup as documented in [docs/deployment.md](docs/deployment.md).
- API contracts, request/response validation, and WebSocket event distribution.
- PostgreSQL database schemas, Alembic migrations, and transactional outbox mechanics.
- Celery worker orchestration and Judge0 CE provider integration.
- Monaco Editor integration, autosave concurrency, and ICPC scoring logic.
- Hybrid proctoring client pipelines (face presence, browser focus, periodic screenshot capture).

### What We Do NOT Support:
- Solutions or hints for algorithmic programming contest problems.
- Custom non-standard compiler configurations outside supported Judge0 runtimes.
- Browser extensions or ad-blockers that intentionally interfere with browser proctoring APIs (`getDisplayMedia`, `getUserMedia`).
- Unofficial forks or unauthorized modifications bypassing security controls.

---

## 3. Incident Severity & Triage SLA

Issues filed in our tracker are categorized according to severity:

| Severity Level | Definition | First Response Target | Resolution Target |
|---|---|---|---|
| **P0 — Critical** | Live contest halted, database corruption, security breach, submissions lost. | < 2 hours | Immediate emergency fix / hotfix |
| **P1 — High** | Judge workers degraded, submission queue backlogged, proctor alerts failing. | < 6 hours | < 24 hours |
| **P2 — Medium** | Non-critical UI glitch, leaderboard rendering bug, draft autosave edge case. | < 2 business days | Next sprint release |
| **P3 — Low** | Documentation typo, cosmetic styling imperfection, enhancement proposal. | Best effort | Backlog triage |

---

## 4. How to Submit a High-Quality Bug Report

When reporting a bug, please ensure the following details are included:
1. **Component**: e.g. `Backend API`, `Celery Judge Worker`, `Monaco Editor`, `WebSocket Hub`.
2. **Environment**: Operating System, Docker version, browser version (Chrome/Edge), deployment mode (Local Compose / Production).
3. **Steps to Reproduce**: Minimal, deterministic steps to trigger the defect.
4. **Expected Behavior**: What should have happened according to the SRS baseline.
5. **Actual Behavior**: What actually happened, including relevant error logs, request IDs, or stack traces.
6. **Logs / Payloads**: Sanitized request/response JSON (ensure passwords and private tokens are redacted).
