# Competitive Programming Platform — Deployment & Operations Guide

| Property | Value |
|---|---|
| Document Version | 1.1 |
| Status | Implementation Baseline |
| Target Scale | 500 concurrent participants, 200 submission burst |
| Container Platform | Docker & Docker Compose v2 |
| Orchestration Ready | Kubernetes / Docker Swarm |

---

## 1. Hardware & System Prerequisites

### 1.1 Sizing Guidelines
| Environment | Concurrent Users | CPU Allocation | RAM Allocation | Storage |
|---|:---:|:---:|:---:|---|
| **Local Development** | 1–10 | 4 vCPU | 8 GB | 20 GB SSD |
| **Staging & Benchmarking** | 100–200 | 8 vCPU | 16 GB | 50 GB NVMe |
| **Production Baseline** | 500 | 16–32 vCPU | 32–64 GB | 200 GB High-IOPS NVMe |

### 1.2 System Dependencies
- **Docker Engine**: Version 24.0+
- **Docker Compose**: Version 2.20+
- **Linux Kernel**: Linux 5.15+ (required for Judge0 cgroups v2 / namespaces isolation)
- **Object Storage**: AWS S3, Cloudflare R2, or local MinIO (S3-compatible)

---

## 2. Containerized Architecture & Services

The deployment is partitioned into modular, independently scalable services:

```mermaid
flowchart TD
    subgraph INGRESS [Reverse Proxy & Load Balancing]
        NGINX[Nginx (Ports 80 / 443)]
    end

    subgraph WEB_SERVICES [Application Tier]
        FRONTEND[Next.js Web (Port 3000)]
        BACKEND[FastAPI API (Port 8000)]
    end

    subgraph WORKERS [Independent Asynchronous Workers]
        WORKER_JUDGE[Celery Judge Worker (judge_queue, run_queue)]
        WORKER_PROCTOR[Celery Proctor Worker (proctor_queue)]
        WORKER_NOTIFY[Celery Notify Worker (notify_queue)]
        SCHEDULER[Single-Leader Scheduler]
        RECONCILER[Outbox & State Reconciler]
    end

    subgraph STATE [Persistence Tier]
        POSTGRES[(PostgreSQL 16)]
        REDIS[(Redis 7 AOF)]
        MINIO[(MinIO / S3 Evidence)]
    end

    subgraph EXECUTION [Judging Tier]
        JUDGE0_SERVER[Judge0 CE Server (Port 2358)]
        JUDGE0_WORKERS[Judge0 Execution Workers]
    end

    NGINX --> FRONTEND
    NGINX --> BACKEND

    BACKEND --> POSTGRES
    BACKEND --> REDIS
    BACKEND --> MINIO

    WORKER_JUDGE --> REDIS
    WORKER_JUDGE --> POSTGRES
    WORKER_JUDGE --> JUDGE0_SERVER

    WORKER_PROCTOR --> REDIS
    WORKER_PROCTOR --> POSTGRES
    WORKER_PROCTOR --> MINIO

    WORKER_NOTIFY --> REDIS

    SCHEDULER --> POSTGRES
    RECONCILER --> POSTGRES
    RECONCILER --> REDIS

    JUDGE0_SERVER --> JUDGE0_WORKERS
```

---

## 3. Quickstart: Local Environment Deployment

### Step 1: Clone & Configure Environment
```bash
git clone https://github.com/organization/competitive-programming-platform.git
cd competitive-programming-platform
cp .env.example .env
```
*(Review and populate `.env` with secure keys and secrets as described in Section 4).*

### Step 2: Build & Start All Services
```bash
docker compose up -d --build
```

### Step 3: Run Database Migrations
```bash
docker compose exec backend alembic upgrade head
```

### Step 4: Seed Languages & Initial Roles
```bash
docker compose exec backend python -m app.scripts.seed_initial_data
```

### Step 5: Verify Service Health
- **Frontend**: `http://localhost:3000`
- **Backend API Docs**: `http://localhost:8000/docs`
- **Judge0 System Info**: `http://localhost:2358/system_info`
- **MinIO Console**: `http://localhost:9001` (Default credentials in `.env`)

---

## 4. Key Configuration Parameters (`.env`)

| Variable | Description | Default / Example |
|---|---|---|
| `POSTGRES_SERVER` | PostgreSQL host | `postgres` |
| `POSTGRES_PORT` | PostgreSQL port | `5432` |
| `POSTGRES_DB` | Database name | `cp_platform` |
| `POSTGRES_USER` | Database user | `postgres` |
| `POSTGRES_PASSWORD` | Strong DB password | *Change in production* |
| `REDIS_URL` | Redis connection URL | `redis://redis:6379/0` |
| `JWT_SECRET_KEY` | 256-bit secret for signing access JWTs | *Generate via `openssl rand -hex 32`* |
| `JUDGE0_URL` | Base URL of Judge0 API | `http://judge0-server:2358` |
| `JUDGE0_CALLBACK_SECRET` | Shared secret for verifying Judge0 webhooks | *Strong random string* |
| `S3_ENDPOINT_URL` | S3 API endpoint | `http://minio:9000` or AWS endpoint |
| `S3_BUCKET_EVIDENCE` | S3 bucket for proctoring screenshots | `cp-evidence-screenshots` |
| `S3_BUCKET_TESTCASES`| S3 bucket for large hidden test cases | `cp-hidden-testcases` |
| `SMTP_HOST` | Outbound email SMTP server | `email-smtp.us-east-1.amazonaws.com` |

---

## 5. Contest Day Runbook

### 5.1 Pre-Contest Checklist (T - 2 Hours)
- [ ] **Verify Judge0 Capacity**: Execute the Phase 0 benchmark script (`python -m tests.benchmarks.judge_capacity`) to verify that the cluster achieves ≥ 25 executions/sec.
- [ ] **Test Case Integrity**: Confirm all assigned problems have valid problem versions and verified sample/hidden test cases.
- [ ] **Object Storage Access**: Test presigned upload and download URLs against S3/MinIO.
- [ ] **Connection Pool Headroom**: Verify PostgreSQL `max_connections` is sized for backend instances ($500 \text{ users} \times 0.1 \approx 50 \text{ connections}$) and workers.
- [ ] **Scheduler Leadership**: Confirm in backend logs that the Single-Leader Scheduler has acquired `pg_try_advisory_lock`.

### 5.2 Live Contest Operations (Contest Window)
- **Grafana Live Dashboard**: Monitor:
  - API P95 Latency (Target: <500 ms).
  - Active WebSocket connections (Target: ~500).
  - Celery `judge_queue` depth (should drain rapidly after submission bursts).
  - Judge execution wait time.
- **Handling Inquiries**: If an organizer manually freezes the leaderboard, confirm `leaderboard_frozen = True` and verify that submissions continue judging in the background.

### 5.3 Post-Contest Draining & Finalization (Contest End)
- **Cutoff Enforcement**: Confirm that API immediately rejects submissions with timestamps $\ge \text{end\_time}$.
- **Drain Judging Queue**: Allow workers to finish all accepted pre-deadline submissions.
- **Final Standings Certification**:
  1. Once all jobs are terminal, the scheduler computes official standings.
  2. Final snapshot `FINAL_OFFICIAL` is generated.
  3. Contest transitions to `COMPLETED`.
  4. Final leaderboard broadcast to all WebSocket clients.

---

## 6. Disaster Recovery & Emergency Procedures

### 6.1 Redis Restart or Queue Flush
1. Because the **Transactional Outbox** persists every accepted submission to PostgreSQL, Redis memory loss does NOT destroy submissions.
2. Restart Redis: `docker compose restart redis`.
3. The `reconciler` daemon automatically identifies pending outbox events and re-enqueues them to Celery.

### 6.2 Judge0 Worker Crash
1. Celery tasks use `acks_late=True`. If a worker dies mid-execution, the task returns to the queue.
2. The `reconciler` checks for `judge_jobs` stuck in `RUNNING` for > 2 minutes and retries them safely.
