# Competitive Programming Platform — API Specification & Contract

| Property | Value |
|---|---|
| Document Version | 1.1 |
| Status | Implementation Baseline |
| Base URL | `/api/v1` |
| WebSocket Base URL | `/api/v1/ws` |
| Authentication | Secure HttpOnly Cookie (`access_token` JWT) + CSRF token header (`X-CSRF-Token`) |
| Content Type | `application/json` |

---

## 1. Global Conventions & Standards

### 1.1 Base URL & Content Negotiation
All REST endpoints reside under `/api/v1`. Both request bodies and responses use standard UTF-8 encoded JSON (`application/json`) unless explicitly specified otherwise (e.g. CSV exports, multipart uploads).

### 1.2 Authentication & Session Flow
1. **Access Tokens**: Short-lived JSON Web Tokens (15-minute expiration) delivered in a `Secure`, `HttpOnly`, `SameSite=Lax` (or `Strict` where appropriate) cookie named `access_token`.
2. **Refresh Tokens**: Opaque tokens rotated on every refresh, delivered in a `Secure`, `HttpOnly` cookie named `refresh_token`, with SHA-256 hashes persisted in the database.
3. **CSRF Protection**: For state-changing requests (`POST`, `PUT`, `PATCH`, `DELETE`), callers must provide the header `X-CSRF-Token` containing the value stored in the non-HttpOnly readable cookie `csrf_token` (Double-Submit Cookie pattern).
4. **WebSocket Authentication**: WebSockets authenticate via either the active HttpOnly cookie handshake or a single-use ticket acquired via `POST /api/v1/auth/ws-ticket`.

### 1.3 Standard Error Format
All errors return a deterministic, structured JSON object:

```json
{
  "error": {
    "code": "CONTEST_ENDED",
    "message": "This contest is no longer accepting submissions.",
    "details": {
      "contest_id": "9b1deb4d-3b7d-4bad-9bdd-2b0d7b3dcb6d",
      "end_time": "2026-11-13T12:00:00Z",
      "received_at": "2026-11-13T12:00:01.428Z"
    },
    "request_id": "c1f7a2d8-4f76-4f40-8f92-574345d81b9e"
  }
}
```

#### Standard Error Codes:
| HTTP Status | Error Code | Description |
|---|---|---|
| 400 | `BAD_REQUEST` | Malformed syntax or request invariants violated. |
| 401 | `UNAUTHENTICATED` | Missing, expired, or invalid session or JWT. |
| 403 | `UNAUTHORIZED` | Authenticated actor lacks required role or resource ownership. |
| 404 | `NOT_FOUND` | Resource does not exist or access is forbidden without disclosure. |
| 409 | `STATE_CONFLICT` | Version mismatch, optimistic lock collision, or invalid lifecycle state. |
| 422 | `VALIDATION_FAILED` | Pydantic schema validation failure on request payload. |
| 429 | `RATE_LIMIT_EXCEEDED` | Request throttled by Redis token-bucket limiter. |
| 500 | `INTERNAL_SERVER_ERROR` | Unhandled backend exception with logged request ID. |
| 502 / 503 | `JUDGE_UNAVAILABLE` | External execution backend (Judge0) unreachable or saturated. |

### 1.4 Cursor-Based Pagination
Collection endpoints return cursor-based pagination metadata:

```json
{
  "items": [ /* array of resource objects */ ],
  "pagination": {
    "limit": 20,
    "next_cursor": "eyJjcmVhdGVkX2F0IjogIjIwMjYtMTEtMTNUMTA6MzA6MDBaIiwgImlkIjogInV1aWQifQ==",
    "has_more": true
  }
}
```
Query parameters:
- `limit` (int, default 20, max 100): Page size.
- `cursor` (string, optional): Base64-encoded cursor returned from previous query.
- `sort` (string, default `created_at`): Field to order by.
- `order` (string, `ASC` or `DESC`, default `DESC`).

---

## 2. Authentication & User Management

### `POST /auth/register`
Creates a new participant account. Sends email verification token.

- **Request Body**:
  ```json
  {
    "username": "coder_pro",
    "email": "coder@example.com",
    "full_name": "Alex Mercer",
    "password": "CorrectHorseBatteryStaple123!"
  }
  ```
- **Response**: `201 Created`
  ```json
  {
    "id": "f47ac10b-58cc-4372-a567-0e02b2c3d479",
    "username": "coder_pro",
    "email": "coder@example.com",
    "full_name": "Alex Mercer",
    "email_verified": false,
    "created_at": "2026-11-13T10:00:00Z"
  }
  ```

### `POST /auth/login`
Authenticates user, issues access/refresh cookies, and returns user identity.

- **Request Body**:
  ```json
  {
    "identity": "coder_pro",
    "password": "CorrectHorseBatteryStaple123!"
  }
  ```
- **Response Headers**:
  `Set-Cookie: access_token=...; HttpOnly; Secure; SameSite=Lax; Path=/`  
  `Set-Cookie: refresh_token=...; HttpOnly; Secure; SameSite=Lax; Path=/api/v1/auth`  
  `Set-Cookie: csrf_token=...; Secure; SameSite=Lax; Path=/`
- **Response**: `200 OK`
  ```json
  {
    "user": {
      "id": "f47ac10b-58cc-4372-a567-0e02b2c3d479",
      "username": "coder_pro",
      "email": "coder@example.com",
      "roles": ["PARTICIPANT"],
      "email_verified": true
    }
  }
  ```

### `POST /auth/refresh`
Rotates refresh token and issues new access token.

- **Response**: `200 OK` (New cookies set).

### `POST /auth/logout`
Revokes active session and clears cookies.

- **Response**: `200 OK`

### `POST /auth/verify-email`
Verifies user email using the token received via email.

- **Request Body**:
  ```json
  {
    "token": "raw-email-verification-token-string"
  }
  ```
- **Response**: `200 OK`

### `POST /auth/forgot-password` & `POST /auth/reset-password`
Standard password reset flow with rate-limited email tokens.

### `GET /auth/me`
Fetches authenticated user identity, active permissions, and roles.

### `GET /auth/sessions` & `DELETE /auth/sessions/{id}`
Allows user to view active device sessions and revoke individual sessions.

---

## 3. Contest Management

### `GET /contests`
Public listing of published contests (supports filters: `status=LIVE|SCHEDULED|COMPLETED`, `visibility=PUBLIC`).

### `POST /contests`
Creates a contest draft (Role: `ORGANIZER`, `ADMIN`, `SUPER_ADMIN`).

- **Request Body**:
  ```json
  {
    "slug": "autumn-clash-2026",
    "title": "Autumn Algorithmic Clash 2026",
    "description": "ICPC-style contest for collegiate developers.",
    "start_time": "2026-11-20T14:00:00Z",
    "end_time": "2026-11-20T16:00:00Z",
    "registration_deadline": "2026-11-20T13:30:00Z",
    "visibility": "PUBLIC",
    "max_participants": 500,
    "scoring_type": "ICPC",
    "wrong_penalty_minutes": 20,
    "freeze_starts_at": "2026-11-20T15:00:00Z",
    "allowed_languages": ["cpp17", "python3", "java17"],
    "proctoring_config": {
      "mode": "BROWSER_WEBCAM_SCREEN",
      "screenshot_interval_seconds": 60,
      "require_fullscreen": true
    }
  }
  ```
- **Response**: `201 Created`

### `PATCH /contests/{id}`
Updates contest settings (Draft status only).

### `POST /contests/{id}/publish`
Transitions contest from `DRAFT` to `SCHEDULED`.

### `POST /contests/{id}/register`
Registers the authenticated user for the contest. Enforces registration deadline, capacity, and account suspension check.

### `POST /contests/{id}/enter`
Participant enters contest workspace. Validates `start_time <= now < end_time` and creates/resumes single `contest_session`.

- **Response**: `200 OK`
  ```json
  {
    "session_id": "7c9e6679-7425-40de-944b-e07fc1f90ae7",
    "contest_id": "autumn-clash-2026",
    "server_time": "2026-11-20T14:05:00Z",
    "contest_start_time": "2026-11-20T14:00:00Z",
    "contest_end_time": "2026-11-20T16:00:00Z",
    "remaining_seconds": 6900,
    "proctoring_status": "PENDING_CONSENT"
  }
  ```

### `POST /contests/{id}/heartbeat`
Session heartbeat every 15–30 seconds. Authoritative for connectivity tracking.

---

## 4. Problem & Test Case Management

### `POST /problems`
Creates a master problem record with unique problem code.

### `POST /problems/{id}/versions`
Creates a new draft version of a problem statement, limits, and configuration.

- **Request Body**:
  ```json
  {
    "title": "Subarray Sum Queries",
    "statement": "Given an array of integers $A$ of length $N$, answer $Q$ queries...",
    "input_format": "The first line contains $N$ and $Q$...",
    "output_format": "Print the answer for each query on a new line.",
    "constraints": "$1 \\le N, Q \\le 10^5$",
    "difficulty": "MEDIUM",
    "tags": ["data-structures", "segment-tree"],
    "time_limit_ms": 1000,
    "memory_limit_mb": 256
  }
  ```
- **Response**: `201 Created`

### `POST /problem-versions/{id}/test-cases`
Adds test case to problem version. Supports inline text or S3 object keys for large data.

- **Request Body**:
  ```json
  {
    "is_sample": true,
    "test_order": 1,
    "input_data": "5 2\n1 2 3 4 5\n1 3\n2 5\n",
    "expected_output_data": "6\n14\n"
  }
  ```

### `POST /problem-versions/{id}/publish`
Locks version immutably (`published_at` set). Once published, cannot be edited.

### `POST /contests/{id}/problems`
Links an immutable `problem_version_id` to a contest with a label (e.g. "A", "B", "C") and display order.

---

## 5. Online Coding Environment & Code Drafts

### `GET /languages`
Lists all enabled Judge0 execution languages supported on the platform.

### `GET /drafts/{contestId}/{problemVersionId}`
Retrieves active code draft for current participant.

- **Response**: `200 OK`
  ```json
  {
    "source_code": "#include <bits/stdc++.h>\n...",
    "language_id": "cpp17-uuid",
    "version": 4,
    "updated_at": "2026-11-20T14:15:20Z"
  }
  ```

### `PUT /drafts/{contestId}/{problemVersionId}`
Autosaves code draft with optimistic concurrency control.

- **Request Body**:
  ```json
  {
    "source_code": "#include <bits/stdc++.h>\n...",
    "language_id": "cpp17-uuid",
    "expected_version": 4
  }
  ```
- **Response**: `200 OK` (returns updated version `5`).
- **Conflict**: `409 Conflict` if `expected_version` does not match the database version (multi-tab collision).
  ```json
  {
    "error": {
      "code": "DRAFT_CONFLICT",
      "message": "A newer draft version exists.",
      "details": { "current_version": 5, "submitted_version": 4 }
    }
  }
  ```

---

## 6. Submissions & Code Execution

### `POST /submissions`
Submits code for authoritative ICPC judging against hidden test suite.

- **Headers**:
  `Idempotency-Key: <UUID>` (Client-generated unique string)
- **Request Body**:
  ```json
  {
    "contest_id": "autumn-clash-2026",
    "contest_problem_id": "a4d31e9c-8f92-4d56-b3c7-123456789abc",
    "language_id": "cpp17-uuid",
    "source_code": "#include <iostream>\nusing namespace std;\nint main(){ return 0; }"
  }
  ```
- **Response**: `202 Accepted`
  ```json
  {
    "submission_id": "d3b07384-d113-469b-9c9e-56e64d2626e9",
    "verdict": "PENDING",
    "submitted_at": "2026-11-20T14:22:15.120Z"
  }
  ```
- **Cutoff Rule**: If server receipt time `>= contest.end_time`, returns `400 Bad Request` with code `CONTEST_ENDED`.

### `POST /submissions/run`
Executes sample or custom input for testing in the IDE. Low priority queue, rate-limited (1 request / 5 seconds). Does not affect contest rankings.

- **Request Body**:
  ```json
  {
    "contest_problem_id": "a4d31e9c-8f92-4d56-b3c7-123456789abc",
    "language_id": "cpp17-uuid",
    "source_code": "...",
    "custom_input": "5 2\n1 2 3 4 5\n"
  }
  ```
- **Response**: `200 OK`
  ```json
  {
    "status": "COMPLETED",
    "stdout": "6\n",
    "stderr": "",
    "compile_output": "",
    "execution_time_ms": 12,
    "memory_used_kb": 1240
  }
  ```

### `GET /submissions/{id}`
Returns submission verdict, execution metrics, and (for samples/custom) outputs. Hidden test outputs are NEVER exposed.

### `POST /submissions/{id}/rejudge`
(Role: `ORGANIZER`, `ADMIN`) Triggers controlled rejudging with mandatory audited reason.

---

## 7. Leaderboards & Freezing

### `GET /contests/{id}/leaderboard`
Fetches current public standings. If contest is frozen, returns the immutable public frozen snapshot.

- **Response**: `200 OK`
  ```json
  {
    "contest_id": "autumn-clash-2026",
    "is_frozen": false,
    "standings": [
      {
        "rank": 1,
        "participant_id": "uuid-1",
        "username": "tourist_fan",
        "problems_solved": 3,
        "total_penalty": 145,
        "last_accepted_at": "2026-11-20T15:12:00Z",
        "problem_results": {
          "A": { "solved": true, "penalty": 24, "wrong_attempts": 0 },
          "B": { "solved": true, "penalty": 41, "wrong_attempts": 1 },
          "C": { "solved": true, "penalty": 80, "wrong_attempts": 2 }
        }
      }
    ]
  }
  ```

### `POST /contests/{id}/leaderboard/freeze`
Freezes public standings (Role: `ORGANIZER`, `ADMIN`). Submissions and internal official scoring continue.

### `POST /contests/{id}/leaderboard/unfreeze`
Reveals latest official standings to public.

### `POST /contests/{id}/leaderboard/finalize`
Finalizes official results after all pre-deadline submissions reach terminal states.

---

## 8. Hybrid Proctoring & Evidence

### `POST /proctoring/sessions`
Records participant consent for monitoring (browser, webcam, screen).

### `POST /proctoring/events`
Batch ingest client-reported proctoring events with client timestamps and event payloads.

- **Request Body**:
  ```json
  {
    "session_id": "7c9e6679-7425-40de-944b-e07fc1f90ae7",
    "events": [
      {
        "event_type": "TAB_FOCUS_LOST",
        "client_timestamp": "2026-11-20T14:35:10Z",
        "metadata": { "reason": "window_blur" }
      },
      {
        "event_type": "WEBCAM_MULTIPLE_FACES",
        "client_timestamp": "2026-11-20T14:35:12Z",
        "metadata": { "face_count": 2 }
      }
    ]
  }
  ```
- **Response**: `202 Accepted`

### `POST /proctoring/evidence`
Requests presigned private S3 upload URL for a periodic 60-second screenshot.

- **Request Body**:
  ```json
  {
    "session_id": "7c9e6679-7425-40de-944b-e07fc1f90ae7",
    "file_size": 45200,
    "content_type": "image/jpeg"
  }
  ```
- **Response**: `200 OK`
  ```json
  {
    "evidence_id": "evidence-uuid",
    "upload_url": "https://s3.private.internal/bucket/screenshots/evidence-uuid.jpg?X-Amz-Signature=..."
  }
  ```

### `GET /proctoring/sessions/{id}` & `GET /proctoring/events`
Proctor dashboard endpoints for inspecting timelines, suspicion scores, and presigned evidence viewing URLs.

### `POST /proctoring/sessions/{id}/warning`
Sends in-app warning banner to participant.

### `POST /proctoring/sessions/{id}/disqualify`
Disqualifies participant with recorded reason (Role: `ORGANIZER`, `ADMIN` with contest authority).

---

## 9. Appeals & Notifications

### `POST /appeals`
Participant submits appeal against a disciplinary action or disqualification.

### `POST /appeals/{id}/review`
Organizer or Admin reviews and accepts/rejects appeal.

### `GET /notifications` & `PATCH /notifications/{id}/read`
Retrieves and updates in-app notification status.

---

## 10. WebSocket Contract: `/api/v1/ws/contests/{contest_id}`

### 10.1 Handshake & Authentication
The WebSocket connection initiates at `wss://<host>/api/v1/ws/contests/{contest_id}`.
Authentication is validated during HTTP upgrade using cookies or `?ticket=<single_use_ticket>`.
Upon successful connection, the server sends a connection confirmation:
```json
{
  "type": "connection.established",
  "data": {
    "connection_id": "conn_1849202",
    "server_time": "2026-11-20T14:00:01Z",
    "contest_status": "LIVE"
  }
}
```

### 10.2 Heartbeat Ping/Pong
To maintain connection liveness and traverse NAT/load balancers:
- Client or server sends: `{"type": "ping"}` every 20 seconds.
- Counterparty responds: `{"type": "pong"}`.
- Failure to receive pong within 45 seconds terminates the socket.

### 10.3 Inbound Client Messages
Participants may emit lightweight presence updates:
```json
{
  "type": "presence.heartbeat",
  "data": {
    "session_id": "7c9e6679-7425-40de-944b-e07fc1f90ae7"
  }
}
```

### 10.4 Outbound Server Broadcast Events

| Event Type | Channel Scope | Payload Description |
|---|---|---|
| `contest.started` | Public contest room | Notifies all clients that contest window has begun. |
| `contest.announcement` | Public contest room | System or organizer announcement text. |
| `submission.updated` | Private participant channel | Submission verdict updates (`PENDING` -> `ACCEPTED` / `WA`). |
| `leaderboard.updated` | Public contest room | Delta or summary notification of standings recalculation. |
| `leaderboard.frozen` | Public contest room | Notification that public standings are now frozen. |
| `leaderboard.unfrozen` | Public contest room | Notification that latest standings are revealed. |
| `proctoring.alert` | Private proctor channel | High-severity proctoring event notification. |
| `proctoring.warning` | Private participant channel | Warning message from proctor/organizer. |
| `contest.completed` | Public contest room | Final standings finalized and contest concluded. |

#### Example `submission.updated` Payload:
```json
{
  "type": "submission.updated",
  "data": {
    "submission_id": "d3b07384-d113-469b-9c9e-56e64d2626e9",
    "contest_problem_id": "a4d31e9c-8f92-4d56-b3c7-123456789abc",
    "problem_label": "A",
    "verdict": "ACCEPTED",
    "execution_time_ms": 45,
    "memory_used_kb": 2340,
    "judged_at": "2026-11-20T14:22:18Z"
  }
}
```
