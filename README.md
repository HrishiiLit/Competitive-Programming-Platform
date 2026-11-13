# Competitive Programming Platform with Hybrid Proctoring

[![Version](https://img.shields.io/badge/version-1.1%20Baseline-blue.svg)](docs/SRS.md)
[![License](https://img.shields.io/badge/license-MIT-green.svg)](LICENSE)
[![Architecture](https://img.shields.io/badge/architecture-Modular%20Monolith-orange.svg)](docs/architecture.md)
[![Target Scale](https://img.shields.io/badge/target%20scale-500%20concurrent%20users-purple.svg)](docs/SRS.md)
[![Judging](https://img.shields.io/badge/judge-Judge0%20CE-red.svg)](docs/judging.md)

An enterprise-grade, public competitive programming platform engineered for collegiate and open algorithmic programming contests with ICPC-style scoring and privacy-first hybrid proctoring.

---

## 🌟 Executive Overview

The platform enables organizers to create, manage, and host algorithmic contests while allowing participants to register, solve problems in an integrated online IDE (Monaco Editor), submit solutions evaluated against hidden test suites, and track standings on live, freezable leaderboards.

### Three Primary Capabilities:
1. **Competitive Programming Engine**: Fixed-window contest sessions, immutable problem versioning, Judge0 CE execution adapter, normalized output comparator, and strict ICPC binary scoring (20-minute wrong attempt penalties, 4-tier deterministic tie-breaking).
2. **Contest Administration**: Organizer & Proctor management dashboards, real-time participant statistics, problem authoring, announcement broadcasting, and certified final result exports.
3. **Hybrid Proctoring & Integrity Layer**: In-browser activity tracking (tab focus, full-screen enforcement, copy/paste logging), client-side sampled face presence detection, periodic downscaled screen capture (640×360 JPEG <100KB uploaded to private S3), and a human-in-the-loop proctor review & appeals workflow.

---

## 🏗️ Architecture & Technology Stack

The platform is designed as a **Modular Monolith** for business logic, backed by **independent asynchronous workers** to guarantee fault isolation, high ingestion throughput, and self-healing resilience:

```mermaid
flowchart TB
    USERS[Participants / Organizers / Proctors] --> NGINX[Nginx Reverse Proxy]
    
    subgraph APP_TIER [Application Layer]
        NEXT[Next.js 14+ Frontend (Monaco Editor)]
        FASTAPI[FastAPI Backend (/api/v1, /api/v1/ws)]
    end

    subgraph DATA_TIER [Durable Persistence]
        PG[(PostgreSQL 16 Primary)]
        OUTBOX[(Transactional Outbox)]
        S3[(Private S3 Storage)]
    end

    subgraph QUEUE_TIER [Queues & Pub/Sub]
        REDIS[(Redis 7 AOF)]
    end

    subgraph WORKERS [Independent Worker Cluster]
        JUDGE_W[Judge Worker (Celery)]
        PROC_W[Proctor Worker (Celery)]
        NOTIFY_W[Notify Worker (Celery)]
        SCHEDULER[Single-Leader Scheduler (PG Advisory Lock)]
        RECONCILER[State & Outbox Reconciler]
    end

    JUDGE0[Judge0 CE Execution Cluster]

    NGINX --> NEXT
    NGINX --> FASTAPI
    FASTAPI --> PG
    FASTAPI --> OUTBOX
    FASTAPI --> S3
    FASTAPI --> REDIS

    OUTBOX -.-> REDIS
    REDIS --> JUDGE_W
    REDIS --> PROC_W
    REDIS --> NOTIFY_W

    JUDGE_W --> JUDGE0
    JUDGE_W --> PG
    PROC_W --> PG
    PROC_W --> S3
    SCHEDULER --> PG
    RECONCILER --> PG
    RECONCILER --> REDIS
```

### Core Technologies:
| Tier | Technology | Purpose |
|---|---|---|
| **Frontend** | Next.js 14+ (React, Tailwind CSS) | Responsive public directory, contestant workspace, dashboards |
| **Code Editor** | Monaco Editor | Syntax highlighting, auto-indentation, C++, Python, Java |
| **State Management** | Zustand & TanStack Query | Client-side reactive UI state and server cache synchronization |
| **Backend API** | Python 3.11+ / FastAPI | High-performance async modular monolith REST & WebSocket APIs |
| **Primary Database** | PostgreSQL 16 | Authoritative source of truth, UUID keys, UTC timestamps |
| **Data Durability** | Transactional Outbox Pattern | Atomic event commits guaranteeing zero lost submissions |
| **Scheduler** | PostgreSQL Session Advisory Locks | Single-leader failover for contest start, end, and auto-freeze |
| **Task Queue & Cache** | Celery + Redis 7 | Independent priority queues (`judge_queue`, `proctor_queue`) |
| **Sandboxed Judge** | Judge0 Community Edition (CE) | Sandboxed code compilation and execution in isolated cgroups |
| **Evidence Storage** | S3-Compatible Storage (MinIO / AWS S3) | Private screenshots with short-lived presigned URLs (7-day lifecycle) |

---

## 📂 Repository Directory Layout

The repository is organized according to the architectural layout specified in Section 18 of the SRS:

```text
cp-platform/
│
├── frontend/                     # Next.js web application
│   ├── app/                      # App router: (public), (auth), (participant), (organizer), admin
│   ├── components/               # UI components: editor, contest, leaderboard, proctoring
│   ├── hooks/                    # Custom React hooks
│   ├── services/                 # API client services & WebSocket connection manager
│   ├── stores/                   # Zustand state stores
│   └── types/                    # Shared TypeScript interfaces
│
├── backend/                      # FastAPI modular monolith
│   ├── app/
│   │   ├── api/                  # Unified routing, middleware, CORS, dependencies
│   │   ├── core/                 # Config, security, DB session, Celery app
│   │   ├── models/               # SQLAlchemy declarative ORM models
│   │   ├── schemas/              # Pydantic v2 request/response schemas
│   │   ├── repositories/         # Database access abstraction
│   │   ├── services/             # Domain logic (auth, contests, judging, scoring, proctoring)
│   │   ├── workers/              # Celery tasks (judge, proctor, notify, reconciler)
│   │   ├── scheduler/            # PostgreSQL advisory-lock-based leader scheduler
│   │   ├── websocket/            # Connection hub, channel dispatch
│   │   └── main.py               # FastAPI entry point
│   ├── migrations/               # Alembic database migrations
│   └── tests/                    # Pytest test suites (unit, integration, benchmarks)
│
├── infrastructure/               # DevOps & deployment assets
│   ├── docker/                   # Dockerfiles for frontend, backend, workers
│   ├── judge0/                   # Judge0 CE configuration & runtime scripts
│   ├── nginx/                    # Nginx reverse proxy configuration
│   └── monitoring/               # Prometheus metrics & Grafana dashboards
│
├── docs/                         # Canonical technical documentation
│   ├── SRS.md                    # Software Requirements Specification (v1.1)
│   ├── architecture.md           # Deep-dive architecture & system design
│   ├── api.md                    # REST & WebSocket API specification
│   ├── openapi.json              # Machine-readable OpenAPI 3.1 schema
│   ├── database.md               # PostgreSQL schema & data dictionary
│   ├── judging.md                # Judge0 integration, output comparator, ICPC scoring
│   ├── proctoring.md             # Hybrid proctoring architecture & privacy rules
│   ├── security.md               # STRIDE threat model & RBAC authorization
│   ├── deployment.md             # Deployment, sizing, and operations runbook
│   └── decisions/                # Architecture Decision Records (ADRs 001–005)
│
├── docker-compose.yml            # Multi-container orchestration stack
├── .env.example                  # Environment configuration template
├── CHANGELOG.md                  # Semantic versioning changelog
├── SUPPORT.md                    # Support policy, triage SLA, bug reporting
├── CONTRIBUTING.md               # Contribution guidelines & coding standards
├── CODE_OF_CONDUCT.md            # Contributor Covenant v2.1 code of conduct
├── SECURITY.md                   # Vulnerability disclosure & security policy
├── LICENSE                       # MIT License
└── README.md                     # Project overview and index
```

---

## 🚀 Quickstart Guide

### Prerequisites
- [Docker Engine](https://docs.docker.com/engine/install/) (v24.0+)
- [Docker Compose](https://docs.docker.com/compose/install/) (v2.20+)
- Python 3.11+ & Node.js 18+ (for local host development)

### 1. Initialize Configuration
```bash
cp .env.example .env
```
*(Review and customize `.env` secrets as needed).*

### 2. Launch Container Stack
```bash
docker compose up -d --build
```
This boots:
- PostgreSQL 16 (Port 5432)
- Redis 7 (Port 6379)
- MinIO Object Storage (API: 9000, Console: 9001)
- Judge0 CE Server & Workers (Port 2358)
- FastAPI Application (Port 8000)
- Celery Workers (`judge-worker`, `proctor-worker`, `notify-worker`)
- Single-Leader Scheduler & Reconciler
- Next.js Frontend (Port 3000)
- Mailpit SMTP Test Server (Web UI: 8025)

### 3. Run Database Migrations & Seeds
```bash
docker compose exec backend alembic upgrade head
docker compose exec backend python -m app.scripts.seed_initial_data
```

### 4. Access Services
- **Web App**: [http://localhost:3000](http://localhost:3000)
- **API Documentation**: [http://localhost:8000/docs](http://localhost:8000/docs)
- **MinIO Console**: [http://localhost:9001](http://localhost:9001) (User: `minioadmin`, Pass: `minioadmin`)
- **Mailpit Web UI**: [http://localhost:8025](http://localhost:8025)

---

## 🔒 15 Mandatory Implementation Constraints

The following 15 rules are strictly enforced across all pull requests and code modifications:

1. **Never execute participant code inside the FastAPI process**: All executions route through sandboxed Judge0 workers.
2. **Never expose hidden test cases** through participant-facing APIs.
3. **Never trust frontend clocks** for contest timing or submission cutoffs.
4. **Never allow Redis to be the sole source of truth** for submissions (always persist via PostgreSQL Transactional Outbox).
5. **Never score the same accepted submission twice** (enforce idempotency).
6. **Never treat Judge0 infrastructure failures as wrong answers** (mark as `SYSTEM_ERROR` and retry).
7. **Never automatically disqualify participants** using algorithmic suspicion scores.
8. **Never allow a proctor to make an unauthorized final disciplinary decision** (restricted to authorized Organizers/Admins).
9. **Never expose evidence** through public object-storage URLs (use short-lived presigned URLs).
10. **Never modify a problem version** used by a historical or live contest.
11. **Never accept submissions** received at or after the authoritative contest cutoff.
12. **Never publish final standings** before all accepted pre-deadline judging jobs are drained.
13. **Never assume that browser-based monitoring detects all external devices**.
14. **Never claim 500-participant production readiness** without benchmark evidence (target: 6,000 executions in ≤ 4 minutes).
15. **Never deploy mandatory proctoring** without an explicit consent and accommodation process.

---

## 📚 Complete Documentation Index

| Document | Description |
|---|---|
| **[docs/SRS.md](docs/SRS.md)** | Canonical Software Requirements Specification (v1.1 Implementation Baseline). |
| **[docs/architecture.md](docs/architecture.md)** | Modular monolith boundaries, transactional outbox, worker topology, scheduler locking. |
| **[docs/api.md](docs/api.md)** | REST API specification, standard error envelopes, and WebSocket broadcast protocol. |
| **[docs/openapi.json](docs/openapi.json)** | Machine-readable OpenAPI 3.1 specification contract. |
| **[docs/database.md](docs/database.md)** | PostgreSQL 16 schema, tables, foreign keys, constraints, and indexes. |
| **[docs/judging.md](docs/judging.md)** | Judge0 integration, batch execution, output normalization, and ICPC scoring. |
| **[docs/proctoring.md](docs/proctoring.md)** | Hybrid proctoring, face presence, 60s screen capture, S3 sizing, DPDP/GDPR compliance. |
| **[docs/security.md](docs/security.md)** | STRIDE threat model, Argon2id, rotating tokens, RBAC matrix, and sandboxing. |
| **[docs/deployment.md](docs/deployment.md)** | Deployment architecture, hardware sizing, contest day runbook, and disaster recovery. |
| **[docs/decisions/](docs/decisions/)** | Architecture Decision Records (ADRs 001 through 005). |
| **[SECURITY.md](SECURITY.md)** | Security disclosure process and contact details. |
| **[CHANGELOG.md](CHANGELOG.md)** | Semantic versioning release history. |
| **[SUPPORT.md](SUPPORT.md)** | Support channels, SLA response targets, and bug reporting guides. |
| **[CONTRIBUTING.md](CONTRIBUTING.md)** | Contribution standards, git conventions, and coding rules. |
| **[CODE_OF_CONDUCT.md](CODE_OF_CONDUCT.md)** | Contributor Covenant v2.1 standards. |
| **[LICENSE](LICENSE)** | MIT Open Source License. |

---

## ⚖️ License

Distributed under the **MIT License**. See [LICENSE](LICENSE) for more information.
