# Competitive Programming Platform — Architecture & System Design

| Property | Value |
|---|---|
| Document Version | 1.1 |
| Status | Implementation Baseline |
| Target Scale | 500 concurrent participants, 200-submission bursts |
| Architecture Pattern | Modular Monolith with Independent Background Workers |

---

## 1. System Overview & Component Topology

The platform provides algorithmic contest hosting, online code execution, real-time leaderboards, and hybrid proctoring. The core engineering philosophy prioritizes **correctness, data durability, and fault recovery**. Code judging and contest state transitions must remain rock-solid regardless of proctoring traffic or network transients.

```mermaid
flowchart TB
    subgraph CLIENT_TIER [Client Applications]
        PARTICIPANT[Participant Browser (Next.js + Monaco)]
        PROCTOR[Proctor / Organizer Console]
        ADMIN[Admin Dashboard]
    end

    subgraph INGRESS [Ingress & Security]
        NGINX[Nginx Reverse Proxy / TLS Termination]
    end

    subgraph APP_TIER [FastAPI Modular Monolith]
        API_ROUTER[API Router (/api/v1)]
        WS_MGR[WebSocket Hub (/api/v1/ws)]
        MODULE_AUTH[Auth & RBAC Module]
        MODULE_CONTEST[Contest Engine]
        MODULE_PROBLEM[Problem & Test Case Module]
        MODULE_SUBMIT[Submission & Outbox Writer]
        MODULE_PROCTOR[Proctoring Event Ingestion]
    end

    subgraph PERSISTENCE [Durable State Tier]
        PG[(PostgreSQL Primary)]
        OUTBOX_TABLE[(Transactional Outbox)]
        S3[(Private S3 / MinIO Evidence Storage)]
    end

    subgraph QUEUE_CACHE [Ephemeral & Queue Tier]
        REDIS_BROKER[(Redis Celery Broker)]
        REDIS_PUBSUB[(Redis Pub/Sub Channel Hub)]
        REDIS_CACHE[(Redis Rate Limiter & Ephemeral Cache)]
    end

    subgraph WORKER_TIER [Independent Worker Cluster]
        DISPATCHER[Outbox Dispatcher Daemon]
        SCHEDULER[Single-Leader Scheduler (PG Advisory Lock)]
        JUDGE_WORKER[Judge Workers (Celery)]
        PROCTOR_WORKER[Proctor Workers (Celery)]
        NOTIFY_WORKER[Notification Workers (Celery)]
        RECONCILER[Submission & State Reconciler]
    end

    subgraph EXTERNAL [External Engines & Gateways]
        JUDGE0[Judge0 CE Code Execution Cluster]
        SMTP[AWS SES / SMTP Provider]
    end

    CLIENT_TIER --> NGINX
    NGINX --> API_ROUTER
    NGINX --> WS_MGR

    API_ROUTER --> MODULE_AUTH
    API_ROUTER --> MODULE_CONTEST
    API_ROUTER --> MODULE_PROBLEM
    API_ROUTER --> MODULE_SUBMIT
    API_ROUTER --> MODULE_PROCTOR

    MODULE_SUBMIT --> PG
    MODULE_SUBMIT --> OUTBOX_TABLE
    MODULE_PROCTOR --> PG
    MODULE_PROCTOR --> S3

    OUTBOX_TABLE -.-> DISPATCHER
    DISPATCHER --> REDIS_BROKER

    REDIS_BROKER --> JUDGE_WORKER
    REDIS_BROKER --> PROCTOR_WORKER
    REDIS_BROKER --> NOTIFY_WORKER

    JUDGE_WORKER --> JUDGE0
    JUDGE_WORKER --> PG
    JUDGE_WORKER --> REDIS_PUBSUB

    PROCTOR_WORKER --> PG
    PROCTOR_WORKER --> S3
    PROCTOR_WORKER --> REDIS_PUBSUB

    NOTIFY_WORKER --> SMTP

    SCHEDULER --> PG
    RECONCILER --> PG
    RECONCILER --> REDIS_BROKER

    WS_MGR <--> REDIS_PUBSUB
```

---

## 2. Modular Monolith Architecture

The backend application is structured as a modular monolith inside `backend/app/`. Each domain module encapsulates its own database entities, business services, and API controllers. Modules communicate via direct Python service interfaces or asynchronously through database transactions.

```text
backend/app/
├── api/                  # Unified FastAPI routing, middleware, error handlers
├── core/                 # Config, security, DB session, Celery client, logging
├── models/               # SQLAlchemy declarative models
├── schemas/              # Pydantic schemas (request/response validation)
├── repositories/         # Database access layer (data mapping and queries)
├── services/             # Domain business logic
│   ├── auth/             # Argon2id, JWT, session lifecycle, RBAC enforcement
│   ├── contests/         # Contest lifecycle, fixed-window timing, registration
│   ├── problems/         # Versioning, test case management, sample validation
│   ├── submissions/      # Cutoff checks, idempotency, outbox insertion
│   ├── judging/          # Judge0 provider adapter, batching, callback handling
│   ├── scoring/          # ICPC penalty calculation, tie-breaking, snapshots
│   ├── proctoring/       # Event processing, cooldowns, suspicion score engine
│   ├── notifications/    # In-app alerts, email queue dispatch
│   └── analytics/        # CSV export, contest metrics, audit querying
├── workers/              # Celery task definitions
├── scheduler/            # PostgreSQL advisory-lock-based leader scheduler
├── websocket/            # Connection manager, channel subscriptions, heartbeat
└── main.py               # Application bootstrap
```

### Module Boundary Rules:
1. **Never perform cross-module writes within unmanaged transactions**: State changes crossing boundaries must be transactional.
2. **Never execute untrusted participant code inside the API process**: Code execution is strictly offloaded to sandboxed Judge0 workers.
3. **Decouple proctoring from judging**: A failure in screenshot upload or face-detection ingestion must NEVER impact submission processing, scoring, or the contest clock.

---

## 3. The Transactional Outbox Pattern

To prevent the **dual-write dilemma** (where writing to PostgreSQL succeeds but pushing to Redis/Celery fails, or vice versa), the system uses the **Transactional Outbox Pattern** for all critical submission and event pipelines.

```mermaid
sequenceDiagram
    autonumber
    actor Participant
    participant API as FastAPI Backend
    participant DB as PostgreSQL
    participant Dispatcher as Outbox Dispatcher
    participant Celery as Redis / Celery
    participant Worker as Judge Worker

    Participant->>API: POST /api/v1/submissions (with Idempotency-Key)
    Note over API: 1. Validate session & contest timing<br/>2. Server-side cutoff check (now < end_time)
    
    rect rgb(240, 248, 255)
    Note over API,DB: Single Atomic Transaction
    API->>DB: INSERT into submissions (status='PENDING')
    API->>DB: INSERT into transactional_outbox (event_type='submission.created')
    DB-->>API: Commit Successful
    end

    API-->>Participant: 202 Accepted {submission_id, verdict: "PENDING"}

    loop Every 200ms or via LISTEN/NOTIFY
        Dispatcher->>DB: SELECT pending events FROM transactional_outbox FOR UPDATE SKIP LOCKED
        Dispatcher->>Celery: Publish task (judge_submission, payload)
        Celery-->>Dispatcher: Acknowledged
        Dispatcher->>DB: UPDATE transactional_outbox SET status='DISPATCHED', processed_at=NOW()
    end

    Celery->>Worker: Consume judge_submission
    Worker->>Worker: Execute judging workflow
```

### Advantages:
- **Zero Lost Submissions**: Even if Redis completely crashes or restarts during a submission spike, every accepted submission is safely persisted in PostgreSQL.
- **Idempotent Queueing**: The outbox record tracks dispatch state (`PENDING`, `DISPATCHED`, `FAILED`).
- **High Ingestion Throughput**: API endpoints only write to PostgreSQL tables without waiting on external queue latency.

---

## 4. Single-Leader Scheduler with PostgreSQL Advisory Locks

Contest lifecycle transitions (`SCHEDULED` → `LIVE`, `LIVE` → `COMPLETED`, automatic leaderboard freeze at `freeze_starts_at`) require strict coordination to prevent race conditions across horizontally scaled FastAPI and worker instances.

### 4.1 Advisory Lock Mechanism
The scheduler runs on all background nodes, but only **one instance** acquires the PostgreSQL application advisory lock:

```python
# scheduler/leader.py
SCHEDULER_LOCK_ID = 84920491823901  # Fixed 64-bit application key

async def run_scheduler_loop(db_session):
    while True:
        # Try acquiring non-blocking session-level advisory lock
        is_leader = await db_session.execute(
            text("SELECT pg_try_advisory_lock(:lock_id)"),
            {"lock_id": SCHEDULER_LOCK_ID}
        ).scalar()

        if is_leader:
            logger.info("Acquired scheduler leadership.")
            try:
                await execute_scheduled_ticks(db_session)
            finally:
                # Kept alive until connection drops or process terminates
                pass
        else:
            logger.debug("Follower node waiting for scheduler leadership...")
        
        await asyncio.sleep(5)
```

### 4.2 Scheduled Responsibilities
1. **Contest Start**: When `server_now >= start_time` and status is `SCHEDULED`, atomically transition to `LIVE`, broadcast `contest.started` on WebSocket, and log audit event.
2. **Contest End**: When `server_now >= end_time` and status is `LIVE`:
   - Immediately reject new submissions at API level.
   - Do NOT mark contest `COMPLETED` immediately if pending submissions exist.
   - Wait until all pre-deadline submissions reach terminal verdicts (`ACCEPTED`, `WA`, `TLE`, etc.).
   - Compute final standings, generate final leaderboard snapshot, set status to `COMPLETED`, and broadcast `contest.completed`.
3. **Automatic Freeze**: When `server_now >= freeze_starts_at` and `leaderboard_frozen == False`:
   - Capture current public standings as a `leaderboard_snapshot`.
   - Set `leaderboard_frozen = True`, record `frozen_public_snapshot_id`.
   - Broadcast `leaderboard.frozen`.

---

## 5. Queue Topology & Worker Specialization

Celery uses Redis as broker with specialized task queues to ensure priority isolation:

| Queue Name | Responsibilities | Concurrency Type | Sizing / Scale |
|---|---|---|---|
| `judge_queue` | Submissions, batch dispatch to Judge0, result polling | Gevent / Async IO | High (independent CPU/IO scaling) |
| `run_queue` | User IDE "Run" sample executions (lower priority) | Gevent / Async IO | Bounded / strict rate-limits |
| `proctor_queue` | Proctoring event aggregation, suspicion scoring, S3 metadata | Prefork / Gevent | Medium |
| `notify_queue` | Emails (verification, password reset, announcements) | Threads | Low to Medium |
| `reconcile_queue`| Periodic outbox cleanup, stuck job reconciliation | Single process | Single instance |

### Priority Policy:
- Contest submissions take priority over rejudging jobs.
- Rejudging jobs take priority over IDE "Run" requests.
- IDE "Run" executions are placed on the separate `run_queue` to ensure high submission loads never starve official contest submissions.

---

## 6. Real-Time WebSocket Architecture

Real-time push delivery to 500+ participants and proctors is managed via FastAPI WebSockets backed by Redis Pub/Sub:

```mermaid
flowchart LR
    API1[FastAPI Node 1] <--> PUBSUB[(Redis Pub/Sub)]
    API2[FastAPI Node 2] <--> PUBSUB
    API3[FastAPI Node 3] <--> PUBSUB

    PUBSUB --> CH_PUBLIC[contest:{id}:public]
    PUBSUB --> CH_USER[contest:{id}:user:{id}]
    PUBSUB --> CH_PROCTOR[contest:{id}:proctors]

    CH_PUBLIC --> CLIENTS_ALL[All Contestants]
    CH_USER --> CLIENT_SINGLE[Target Contestant]
    CH_PROCTOR --> PROCTORS[Assigned Proctors]
```

### Connection Resilience Rules:
- **WebSockets are ephemeral notifications, NOT authoritative records**: If a client disconnects, it reconnects with exponential backoff and immediately queries the REST API for authoritative state (`/contests/{id}/leaderboard`, `/submissions`).
- **Ping/Pong Heartbeats**: Sent every 20 seconds. Sockets inactive for >45 seconds are closed and cleaned up to prevent memory leaks.

---

## 7. Submission Reconciler & Self-Healing

The `reconciler` daemon guarantees system self-healing across infrastructure failures:
1. **Orphaned Outbox Events**: Queries `transactional_outbox` where `status = 'PENDING'` and `created_at < NOW() - INTERVAL '30 seconds'`. Re-publishes task to Celery.
2. **Stuck Judging Jobs**: Queries `judge_jobs` where `job_status = 'RUNNING'` and `started_at < NOW() - INTERVAL '2 minutes'`. Polls Judge0 for token status. If Judge0 lost the token, marks as `RETRY` (up to `max_retries`).
3. **Missing Finalization**: Queries contests where `end_time <= NOW()`, status is `LIVE`, and all judging jobs are completed. Automatically triggers final scoring and completion.
