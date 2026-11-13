# Competitive Programming Platform — Security Architecture & Threat Model

| Property | Value |
|---|---|
| Document Version | 1.1 |
| Status | Implementation Baseline |
| Threat Model Methodology | STRIDE |
| Password Hashing | Argon2id |
| Token Standard | JWT (15-min access) + Hashed Rotating Refresh Tokens |
| Sandboxing Engine | Judge0 CE (cgroups, Linux namespaces, restricted user) |

---

## 1. Trust Boundaries & STRIDE Threat Analysis

```mermaid
flowchart LR
    subgraph UNTRUSTED [Untrusted Zone]
        CLIENT[Participant / Browser Client]
        ATTACKER[Adversary / Infiltrator]
    end

    subgraph DMZ [Ingress Boundary]
        NGINX[Nginx Reverse Proxy / WAF]
    end

    subgraph APP_ZONE [Trusted Application Boundary]
        API[FastAPI Application]
        WORKERS[Celery Workers]
    end

    subgraph DATA_ZONE [Internal Data Boundary]
        PG[(PostgreSQL Primary)]
        REDIS[(Redis Broker & Cache)]
        S3[(Private S3 Storage)]
    end

    subgraph ISOLATION_ZONE [Execution Isolation Boundary]
        JUDGE0[Judge0 Sandbox (No Network, Cgroups)]
    end

    UNTRUSTED -->|HTTPS / WSS| NGINX
    NGINX -->|Reverse Proxy| API
    API -->|SQL (Parametrized)| PG
    API -->|Redis Protocol| REDIS
    API -->|Presigned URLs| S3
    WORKERS -->|Celery Tasks| REDIS
    WORKERS -->|SQL (Parametrized)| PG
    WORKERS -->|REST (Internal)| JUDGE0
```

### 1.1 STRIDE Threat Register
| Threat ID | Category | Component & Boundary | Description | Mitigation Plan |
|---|---|---|---|---|
| **T-01** | Spoofing | Client → API Auth | Stolen or forged session token / JWT forgery. | Short-lived (15-min) JWTs, rotating refresh tokens with DB hashes, `HttpOnly` `Secure` cookies. |
| **T-02** | Tampering | Client → Submissions | Tampering with submission receipt timestamp or verdict. | Timestamps generated solely on PostgreSQL server; verdicts written solely by trusted judge workers. |
| **T-03** | Repudiation | Proctoring & Disciplinary | Participant disputes disqualification or organizer denies action. | Append-only `audit_logs`, mandatory recorded reasons, screenshot hashes stored in DB. |
| **T-04** | Information Disclosure | Contest API → Participant | Leaking hidden test cases or expected outputs. | API schemas strictly exclude hidden test inputs/outputs; only authorized judge workers query test data. |
| **T-05** | Denial of Service | Participant → Submission / Run API | Submission spam flooding Judge0 execution queues. | Redis token-bucket rate limiting (1 submit / 2s; 1 run / 5s), transactional outbox buffering. |
| **T-06** | Elevation of Privilege | Participant → Admin/Organizer APIs | Insecure Direct Object References (IDOR) or role escalation. | Backend RBAC middleware verifying resource ownership (`contest.organizer_id == user.id`). |
| **T-07** | Tampering / Escape | Judge0 → Host Operating System | Malicious C++ / Python payload attempting host breakout or network pivot. | Judge0 runs unprivileged Linux containers, cgroups, seccomp, strict memory/CPU caps, network disabled (`none`). |
| **T-08** | Information Disclosure | Evidence Storage (S3) | Public snooping of proctoring screenshots. | Private S3 buckets with Public Access Block enabled; time-limited presigned GET URLs (15 min) restricted to proctors. |

---

## 2. Authentication & Credential Security

### 2.1 Password Hashing Specification
User passwords are never stored in plaintext. Passwords are hashed using **Argon2id** (RFC 9106) with industry-hardened parameters:
- **Algorithm**: Argon2id
- **Time Cost ($t$)**: 3 iterations
- **Memory Cost ($m$)**: 65,536 KiB (64 MiB)
- **Parallelism ($p$)**: 4 lanes
- **Salt Length**: 16 bytes cryptographically secure random bytes (`os.urandom(16)`)

### 2.2 Token Lifecycle & Session Rotation
1. **Access Token (JWT)**:
   - Contains: `sub` (User UUID), `username`, `roles`, `iat`, `exp`, `jti`.
   - Expiration: **15 minutes**.
   - Storage: `access_token` cookie (`HttpOnly`, `Secure`, `SameSite=Lax`).
2. **Refresh Token**:
   - High-entropy cryptographically secure random string (32 bytes URL-safe base64).
   - Storage: SHA-256 hash stored in `refresh_tokens` table in PostgreSQL.
   - Lifetime: 7 days.
   - **Rotation**: On every call to `POST /auth/refresh`, the old refresh token is marked revoked and a brand-new token pair is issued. If a revoked token is presented, all sessions for that user are immediately invalidated (Breach Detection).
3. **CSRF Protection**:
   - Double-Submit Cookie pattern for state-changing HTTP methods (`POST`, `PUT`, `PATCH`, `DELETE`).
   - The client reads the `csrf_token` cookie and mirrors its value in the `X-CSRF-Token` request header.

---

## 3. Role-Based Access Control (RBAC) & Authorization Matrix

The backend enforces authorization at the router dependency layer:

| Resource & Operation | SUPER_ADMIN | ADMIN | ORGANIZER | PROCTOR | PARTICIPANT |
|---|:---:|:---:|:---:|:---:|:---:|
| System Configuration & Global Audit | ✅ | ❌ | ❌ | ❌ | ❌ |
| User Management & Role Assignment | ✅ | ✅ | ❌ | ❌ | ❌ |
| Create & Publish Contests | ✅ | ✅ | ✅ | ❌ | ❌ |
| Edit Contest Settings | ✅ | ✅ | ✅ (Own contest) | ❌ | ❌ |
| Assign Proctors to Contest | ✅ | ✅ | ✅ (Own contest) | ❌ | ❌ |
| View Assigned Proctoring Timelines | ✅ | ✅ | ✅ (Own contest) | ✅ (Assigned) | ❌ |
| Issue Warnings to Contestants | ✅ | ✅ | ✅ (Own contest) | ✅ (Assigned) | ❌ |
| Issue Final Disqualification | ✅ | ✅ | ✅ (Own contest) | ❌ | ❌ |
| Review Appeals | ✅ | ✅ | ✅ (Own contest) | ❌ | ❌ |
| Submit Code / Autosave Drafts | ❌ | ❌ | ❌ | ❌ | ✅ (Enrolled) |
| View Public Contests & Standings | ✅ | ✅ | ✅ | ✅ | ✅ |

### IDOR Prevention Strategy
All endpoints verifying resource access (e.g. `GET /drafts/{contestId}/{problemVersionId}`) enforce ownership queries:
```python
# app/api/deps.py
async def verify_contest_organizer(contest_id: UUID, current_user: User, db: AsyncSession):
    contest = await db.get(Contest, contest_id)
    if not contest:
        raise HTTPException(status_code=404, detail="Contest not found")
    if current_user.has_role("SUPER_ADMIN", "ADMIN"):
        return contest
    if contest.organizer_id != current_user.id:
        raise HTTPException(status_code=403, detail="Forbidden: You do not own this contest")
    return contest
```

---

## 4. Code Execution Sandboxing (Judge0 CE)

To prevent remote code execution (RCE) and infrastructure compromise:
1. **Network Isolation**: Judge0 execution containers are spawned with `--net=none`. Participant solutions cannot make socket connections, probe the internal Docker network, or contact metadata endpoints (e.g. `169.254.169.254`).
2. **Resource Constraints**:
   - Maximum CPU execution time: Problem-configured (typically 1.0–2.0 seconds).
   - Maximum wall-clock execution time: $2 \times \text{CPU limit} + 1\text{ second}$.
   - Memory limit: Problem-configured (typically 256–512 MB).
   - Maximum output size: 4,096 KB (prevents disk-filling OLE attacks).
   - Maximum processes / threads: Restricted via cgroups PID limit (`pids_limit=30`).
3. **Filesystem Sandbox**: Root filesystem is mounted read-only (`ro`); temporary working directories use ephemeral, size-constrained `tmpfs` mounts.
4. **Unprivileged Execution**: Code executes under unprivileged UID/GID (`nobody`).

---

## 5. Rate Limiting & Denial of Service Defenses

The platform employs Redis-backed sliding-window rate limiters:

| Endpoint Scope | Limit | Window | Action on Violation |
|---|---:|---:|---|
| `/auth/login` | 5 requests | 60 seconds | HTTP 429 + Exponential backoff |
| `/auth/register` | 3 requests | 60 seconds | HTTP 429 |
| `/submissions` (Contest) | 1 request | 2 seconds | HTTP 429 `SUBMISSION_RATE_LIMITED` |
| `/submissions/run` (Custom) | 1 request | 5 seconds | HTTP 429 `RUN_RATE_LIMITED` |
| `/proctoring/events` | 30 requests | 60 seconds | HTTP 429 |
| Global API per IP | 100 requests | 60 seconds | HTTP 429 |

---

## 6. Audit Logging & Non-Repudiation

All security-sensitive operations generate immutable records in the `audit_logs` table:
- Account creation, password changes, and email verifications.
- Role assignments and privilege grants.
- Contest creation, publication, manual freezes, and cancellations.
- Disciplinary actions, warnings, and appeal determinations.
- Problem version publications and test case updates.

Each log entry records: `actor_id`, `action`, `resource_type`, `resource_id`, `ip_address`, `metadata` (JSON diff), and UTC `created_at`.
