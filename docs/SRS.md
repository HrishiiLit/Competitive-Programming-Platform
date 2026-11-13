# Competitive Programming Platform with Hybrid Proctoring
## Software Requirements Specification (SRS)

| Document property | Value |
|---|---|
| Version | 1.1 |
| Status | Implementation baseline |
| Date | 13 November 2026 |
| Product | Public Competitive Programming Platform |
| Primary target | 500 concurrent participants |
| Initial judge | Judge0 CE |
| Architecture | Modular monolith + independent workers |
| Frontend | Next.js |
| Backend | FastAPI |
| Database | PostgreSQL |
| Queue | Celery + Redis |

---

# 1. Executive Summary

## 1.1 Product overview

The proposed system is a public competitive programming platform that enables organizers to create and host algorithmic programming contests while allowing participants to register, solve problems, submit solutions and view rankings through a browser-based interface.

The platform combines three primary capabilities:

1. **Competitive Programming:** Contest management, problem statements, online IDE, automated judging and ICPC-style leaderboards.
2. **Contest Administration:** Organizer dashboards, participant management, live statistics and result publication.
3. **Hybrid Proctoring:** Browser activity monitoring, webcam-based presence detection, screen-sharing verification and suspicious activity investigation.

The platform will integrate an existing code execution engine rather than develop its own compiler and sandbox infrastructure.

The initial release will target 500 concurrent participants, with judging capacity independently benchmarked before production deployment.

## 1.2 Product objectives

- Enable public user registration and secure authentication.
- Allow organizers to independently create and publish contests.
- Support individual competitive programming contests.
- Provide an integrated coding environment.
- Evaluate submissions through Judge0.
- Implement correct ICPC-style scoring.
- Provide real-time contest leaderboards.
- Monitor participants through configurable hybrid proctoring.
- Maintain timestamped evidence and administrative audit trails.
- Support recoverable network interruptions.
- Maintain reliable operation during contest start, submission and end-time traffic spikes.

## 1.3 Finalized product decisions

| Decision | Selected approach |
|---|---|
| Audience | Public |
| Contest type | Individual |
| Contest timing | Fixed-window |
| Proctoring | Browser + webcam + screen |
| Screen evidence | Periodic screenshots |
| Webcam evidence | Client-side detection events; no raw recording in V1 |
| Identity verification | Out of scope for V1 |
| Concurrent participants | 500 |
| Judging | Judge0 CE integration |
| Scoring | ICPC-style, all-or-nothing |
| Frontend | Next.js + React |
| Editor | Monaco Editor |
| Backend | FastAPI |
| Database | PostgreSQL |
| ORM | SQLAlchemy |
| Migrations | Alembic |
| Background jobs | Celery |
| Broker/cache | Redis |
| Real-time communication | WebSockets |
| Authentication | JWT access token + rotating refresh token in secure HTTP-only cookies |
| Scheduler | PostgreSQL advisory-lock-based single leader |
| Evidence storage | Private S3-compatible object storage |
| Deployment | Docker-based |

## 1.4 Assumptions

- A contest is created and administered by an authorized organizer.
- Each participant uses an individual account.
- Every participant has one active contest session per contest.
- Participants use a supported desktop browser for mandatory hybrid-proctored contests.
- Organizers provide valid problem statements and test cases.
- Judge0 is available through a managed or self-hosted deployment with sufficient capacity.
- Internet access is required for contest participation.
- Screen capture and webcam access depend on browser permission and operating-system capabilities.
- The platform does not guarantee detection of every possible cheating method.

---

# 2. Scope

## 2.1 In scope — V1

1. Public registration and authentication.
2. User profiles and role-based access control.
3. Contest creation, publication and scheduling.
4. Public contest discovery.
5. Participant registration.
6. Fixed-window contest sessions.
7. Problem creation and versioning.
8. Hidden test-case management.
9. Monaco-based online IDE.
10. Autosave and draft recovery.
11. Judge0 integration.
12. Asynchronous submission processing.
13. ICPC scoring.
14. Live leaderboard.
15. Leaderboard freezing.
16. Browser activity monitoring.
17. Webcam-based presence monitoring.
18. Screen-sharing monitoring.
19. Periodic screen evidence capture.
20. Proctoring event management.
21. Warnings and disciplinary actions.
22. Appeals.
23. Organizer and proctor dashboards.
24. Notifications.
25. Audit logs.
26. Contest analytics and CSV exports.

## 2.2 Out of scope — V1

- Team contests.
- Virtual contests.
- Public practice arena.
- AI-generated problems.
- AI tutoring.
- Native mobile applications.
- Custom compiler and sandbox development.
- Automatic identity recognition.
- Automatic disqualification based on AI.
- Continuous webcam recording.
- Continuous screen recording.
- Operating-system-level lockdown.
- Public problem marketplace.
- Recruitment assessments.
- Public rating ecosystem.

## 2.3 Future scope

Potential V1.1/V2 capabilities:

- Code plagiarism detection using token fingerprints and AST similarity.
- MOSS-style post-contest similarity reports, subject to appropriate licensing.
- Team-based ICPC contests.
- Virtual contests.
- Practice mode.
- Rating system.
- Advanced analytics.
- Multiple institutions and organizer organizations.
- More sophisticated proctoring analysis.

---

# 3. User roles and permissions

| Role | Permissions |
|---|---|
| SUPER_ADMIN | Complete platform administration |
| ADMIN | User management, contest oversight and platform reports |
| ORGANIZER | Create and manage assigned contests |
| PROCTOR | Monitor assigned contests and review participants |
| PARTICIPANT | Register, join contests and submit code |

## 3.1 Role requirements

- AUTH-001 [Must]: Every authenticated request shall be authorized using backend-enforced permissions.
- AUTH-002 [Must]: Participants shall only access their own drafts, private submissions and account data.
- AUTH-003 [Must]: Organizers shall only modify contests they own or have explicitly been authorized to manage.
- AUTH-004 [Must]: Proctors shall only access contests assigned to them.
- AUTH-005 [Must]: Only ADMIN or SUPER_ADMIN shall assign privileged roles.
- AUTH-006 [Must]: Role changes shall generate immutable audit records.

---

# 4. Functional Requirements

## 4.1 Authentication and user management

### FR-AUTH

- AUTH-010 [Must]: Users shall register using username, email, full name and password.
- AUTH-011 [Must]: Email addresses and usernames shall be unique.
- AUTH-012 [Must]: Email verification shall be required before contest participation.
- AUTH-013 [Must]: Passwords shall be hashed using Argon2id.
- AUTH-014 [Must]: Users shall authenticate using email/username and password.
- AUTH-015 [Must]: Access tokens shall be short-lived JWTs.
- AUTH-016 [Must]: Refresh tokens shall be rotated and stored as hashes in the database.
- AUTH-017 [Must]: Authentication cookies shall use Secure, HttpOnly and appropriate SameSite attributes.
- AUTH-018 [Must]: Cookie-authenticated state-changing requests shall have CSRF protection.
- AUTH-019 [Must]: Users shall be able to reset forgotten passwords through verified email.
- AUTH-020 [Must]: Login, password reset and verification endpoints shall be rate-limited.
- AUTH-021 [Must]: Users shall be able to revoke active sessions through logout and token revocation.
- AUTH-022 [Should]: Users shall be able to view and revoke other active login sessions.

### User profile

- AUTH-023 [Must]: Participants shall have a username, display name, verified email and account status.
- AUTH-024 [Must]: Users shall be able to update permitted profile information.
- AUTH-025 [Must]: Suspended accounts shall be prevented from entering new contests.
- AUTH-026 [Must]: User profile changes shall be validated and audited where appropriate.

## 4.2 Contest management

### Contest configuration

- CON-001 [Must]: Organizers shall be able to create contests.
- CON-002 [Must]: Each contest shall have a unique slug.
- CON-003 [Must]: Each contest shall contain a title, description, start time and end time.
- CON-004 [Must]: Registration shall have a configurable deadline.
- CON-005 [Must]: Organizers shall configure maximum participant capacity.
- CON-006 [Must]: Organizers shall configure visibility as PUBLIC or PRIVATE.
- CON-007 [Must]: Organizers shall configure scoring parameters.
- CON-008 [Must]: Organizers shall select supported programming languages.
- CON-009 [Must]: Organizers shall configure proctoring requirements.
- CON-010 [Must]: Organizers shall configure contest rules.
- CON-011 [Must]: Organizers shall be able to save unpublished contests as drafts.
- CON-012 [Must]: Published contests shall appear in the public contest directory when visibility permits.

### Contest timing model

**Decision: Fixed-window contests.**

All participants share the same contest start and end timestamps.

There will be no participant-specific duration or per-user deadline in V1.

The `duration` field shall not be stored as an independent authoritative timing value. It may be derived from:

`end_time - start_time`

Rules:

1. A contest becomes active at its configured `start_time`.
2. A participant may join after the contest starts, provided the contest has not ended.
3. Late joiners receive only the remaining contest time.
4. Every participant's deadline is the same `end_time`.
5. A participant cannot enter before `start_time`.
6. A participant cannot enter after `end_time`.
7. The server controls all timestamps.
8. A participant who joins late does not receive additional time.
9. A disconnected participant may recover the same contest session before `end_time`.
10. A disconnected participant cannot receive a new full-duration session.

Requirements:

- CON-013 [Must]: Contest start and end timestamps shall be authoritative.
- CON-014 [Must]: The backend shall validate contest eligibility and timing for every session-entry request.
- CON-015 [Must]: Late joining shall be permitted until `end_time`.
- CON-016 [Must]: Contest timers shall use server timestamps rather than client clocks.
- CON-017 [Must]: Submissions received and durably accepted before `end_time` shall remain eligible for judging after the contest ends.
- CON-018 [Must]: Submissions received at or after `end_time` shall be rejected.
- CON-019 [Must]: Contest completion shall wait for all accepted pre-deadline submissions to reach a terminal judging state.
- CON-020 [Must]: The final leaderboard shall not be published until judging is drained and final scoring is complete.

### Contest lifecycle

Supported states:

| State | Description |
|---|---|
| DRAFT | Not published |
| SCHEDULED | Published and awaiting start |
| LIVE | Contest accepting participants and submissions |
| COMPLETED | Judging finalized and results published |
| CANCELLED | Contest cancelled |

A contest shall not have a FROZEN state.

Leaderboard freezing is a separate property and does not stop the contest or submissions.

Requirements:

- CON-021 [Must]: Contest transitions shall be enforced by the backend.
- CON-022 [Must]: Contests shall start automatically using a database-backed scheduler.
- CON-023 [Must]: Contests shall end automatically at `end_time`.
- CON-024 [Must]: A single scheduler leader shall coordinate scheduled transitions using PostgreSQL advisory locks.
- CON-025 [Must]: Contest state transitions shall be idempotent.
- CON-026 [Must]: Organizers shall be able to cancel contests with a recorded reason.
- CON-027 [Must]: A cancelled contest shall reject new submissions.
- CON-028 [Must]: Contest cancellation and result handling shall be recorded in the audit log.

### Registration

- CON-030 [Must]: Participants shall register for a contest before its registration deadline.
- CON-031 [Must]: Duplicate registrations shall be prevented by a database constraint.
- CON-032 [Must]: Capacity limits shall be enforced transactionally.
- CON-033 [Must]: Organizers shall view and export registration lists.
- CON-034 [Must]: Participants shall view their registration status.
- CON-035 [Must]: Private contests shall require an invitation or valid access mechanism.
- CON-036 [Must]: A participant shall not register using a suspended account.

## 4.3 Leaderboard freezing

Freeze is not a contest lifecycle state.

The contest shall contain:

- `freeze_starts_at`
- `frozen_public_snapshot_id`
- `leaderboard_frozen`
- `unfrozen_at`

Rules:

1. The organizer may configure an automatic freeze timestamp.
2. The organizer may manually freeze or unfreeze the leaderboard.
3. The freeze operation shall capture the current public leaderboard snapshot.
4. Submissions and judging shall continue normally.
5. Official internal scores shall continue updating.
6. Participants shall see the frozen public snapshot.
7. Unfreezing shall reveal the latest calculated standings.
8. The final official leaderboard shall be published after contest completion.

Requirements:

- LBF-001 [Must]: Leaderboard freezing shall not stop submissions.
- LBF-002 [Must]: Freeze shall not modify submission verdicts or scoring records.
- LBF-003 [Must]: The public snapshot shall remain consistent throughout the freeze.
- LBF-004 [Must]: Authorized organizers shall be able to view internal standings.
- LBF-005 [Must]: Manual freeze/unfreeze actions shall be audited.
- LBF-006 [Must]: Automatic freezing shall use `freeze_starts_at`, not a separate contest state.

## 4.4 Problem management and versioning

### Problem creation

- PRB-001 [Must]: Organizers shall create problems with unique problem codes.
- PRB-002 [Must]: Each problem shall have a title and Markdown statement.
- PRB-003 [Must]: Problems shall support input format, output format and constraints.
- PRB-004 [Must]: Problems shall support sample inputs and outputs.
- PRB-005 [Must]: Problems shall support hidden test cases.
- PRB-006 [Must]: Problems shall have configurable time and memory limits.
- PRB-007 [Must]: Problems shall support tags and difficulty.
- PRB-008 [Must]: Organizers shall assign problems to contests.
- PRB-009 [Must]: Hidden tests shall not be exposed through participant-facing APIs.

### Problem versioning

A problem may be edited outside a live contest, but the version assigned to a contest must remain immutable.

Requirements:

- PRB-010 [Must]: Every published problem revision shall create an immutable problem version.
- PRB-011 [Must]: A contest shall reference a specific `problem_version_id`.
- PRB-012 [Must]: Problem statements, constraints, resource limits and test cases shall belong to that version.
- PRB-013 [Must]: Editing the original problem shall not change an active or historical contest version.
- PRB-014 [Must]: Rejudging shall use the original contest problem version unless an explicitly audited correction is approved.
- PRB-015 [Must]: Problem-version publication shall be transactional.

### Test cases

- PRB-016 [Must]: Each problem version shall contain ordered test cases.
- PRB-017 [Must]: Test cases shall support sample/hidden visibility.
- PRB-018 [Must]: Test cases shall support secure object-storage references for large inputs.
- PRB-019 [Must]: Hidden expected outputs shall be accessible only to authorized judging workers.
- PRB-020 [Should]: Test cases shall support groups for future partial scoring.

## 4.5 Online coding environment

### Editor

- IDE-001 [Must]: The platform shall use Monaco Editor.
- IDE-002 [Must]: The editor shall support C++, Python and Java.
- IDE-003 [Must]: The editor shall support syntax highlighting and auto-indentation.
- IDE-004 [Must]: The participant shall be able to select a language.
- IDE-005 [Must]: Participants shall be able to execute sample/custom input.
- IDE-006 [Must]: Participants shall be able to submit source code.
- IDE-007 [Must]: The editor shall display submission status and verdict.
- IDE-008 [Must]: The editor shall support a configurable full-screen workspace.

### Code drafts and autosave

- IDE-009 [Must]: Code shall be autosaved every 10 seconds while dirty.
- IDE-010 [Must]: Autosave shall use a 1-second debounce after typing stops.
- IDE-011 [Must]: Drafts shall be associated with contest, participant, problem and language.
- IDE-012 [Must]: Drafts shall be recoverable after page refresh.
- IDE-013 [Must]: Drafts shall be recoverable after a temporary network interruption.
- IDE-014 [Must]: Autosave shall use optimistic concurrency control.
- IDE-015 [Must]: Draft updates shall include a version number.
- IDE-016 [Must]: Conflicting multi-tab updates shall return HTTP 409 and shall not silently overwrite newer code.
- IDE-017 [Should]: The UI shall identify another active editor tab where possible.
- IDE-018 [Must]: Autosave shall not generate judged submissions.

Initial limits:

- Maximum source-code size: 64 KB.
- Autosave interval: 10 seconds.
- Autosave debounce: 1 second.
- Draft persistence: PostgreSQL.

### Run vs Submit

**Run:**

- Executes sample or custom input.
- Does not contribute to leaderboard.
- Has lower queue priority.
- Has stricter per-user rate limits.

**Submit:**

- Evaluates against the complete hidden test suite.
- Creates a permanent submission record.
- Affects scoring when accepted.
- Receives higher queue priority than Run.

Requirements:

- IDE-019 [Must]: Run and Submit shall use separate API operations.
- IDE-020 [Must]: Run shall never reveal hidden test inputs or expected outputs.
- IDE-021 [Must]: Run shall have a lower priority than contest submissions.
- IDE-022 [Must]: Run requests shall be rate-limited.
- IDE-023 [Must]: Submit shall require an active, valid contest session.

## 4.6 Code judging

### Judge integration

The platform shall use Judge0 CE through an internal provider adapter.

- JDG-001 [Must]: Judge0 API calls shall originate only from backend workers.
- JDG-002 [Must]: Judge credentials shall be stored in server-side secrets.
- JDG-003 [Must]: Language identifiers shall be stored in a database table.
- JDG-004 [Must]: Internal submissions shall be independent of Judge0-specific token formats.
- JDG-005 [Must]: Each test execution shall have an independently traceable judge reference.
- JDG-006 [Must]: Hidden tests shall be loaded only by authorized workers.
- JDG-007 [Must]: The system shall use bounded retry policies.
- JDG-008 [Must]: Judge infrastructure failures shall not be interpreted as WA.
- JDG-009 [Must]: Judge responses shall be validated before finalizing a submission.
- JDG-010 [Must]: Duplicate callbacks and polling results shall not cause duplicate scoring.
- JDG-011 [Must]: The system shall support controlled rejudging.
- JDG-012 [Must]: The system shall preserve original and rejudged results in its audit history.

### Verdicts

V1 verdicts:

| Verdict | Meaning |
|---|---|
| PENDING | Waiting in queue |
| JUDGING | Currently executing |
| ACCEPTED | All required tests passed |
| WRONG_ANSWER | Incorrect output |
| TIME_LIMIT_EXCEEDED | Execution exceeded time |
| MEMORY_LIMIT_EXCEEDED | Memory limit exceeded |
| RUNTIME_ERROR | Runtime failure |
| COMPILATION_ERROR | Compilation failed |
| OUTPUT_LIMIT_EXCEEDED | Output limit exceeded |
| SYSTEM_ERROR | Judging infrastructure failure |
| REJUDGING | Re-evaluation in progress |
| INVALIDATED | Previously valid result invalidated through an authorized correction |

### Test aggregation

V1 uses all-or-nothing ICPC scoring.

- All required test cases must pass for ACCEPTED.
- The first meaningful failure shall determine the primary verdict, following a deterministic ordering.
- SYSTEM_ERROR shall override ordinary failure aggregation when the evaluation is incomplete due to infrastructure failure.
- A SYSTEM_ERROR shall never count as WRONG_ANSWER.
- A submission shall be eligible for controlled rejudging.
- Partial scores and test-case weights are reserved for future releases.

### Output comparison

V1 shall use normalized text comparison:

- Normalize CRLF and LF line endings.
- Ignore trailing whitespace at the end of each line.
- Ignore trailing blank lines.
- Preserve meaningful token and line content.
- Do not ignore arbitrary internal whitespace in token-sensitive problems.
- Do not perform floating-point tolerance comparison in the generic comparator.

Problems requiring multiple valid outputs or specialized comparison shall be marked unsupported for generic judging until a custom checker is introduced.

Judge0 CE does not provide a general-purpose custom checker pipeline equivalent to a full online judge. This limitation shall be reflected in organizer documentation.

## 4.7 ICPC scoring

### Scoring model

V1 uses binary ICPC-style scoring.

A problem is either solved or unsolved.

No partial scoring or configurable problem weights shall affect V1 rankings.

### Penalty formula

For each solved problem:

`Problem penalty = floor((accepted_at - contest_start_time) / 60 seconds) + (20 × incorrect_attempts)`

Total participant penalty:

`Total penalty = sum of penalties for solved problems`

An incorrect attempt includes:

- WRONG_ANSWER
- TIME_LIMIT_EXCEEDED
- MEMORY_LIMIT_EXCEEDED
- RUNTIME_ERROR
- OUTPUT_LIMIT_EXCEEDED

The following do not add penalty:

- COMPILATION_ERROR
- SYSTEM_ERROR
- PENDING
- JUDGING
- INVALIDATED
- REJUDGING

Only incorrect attempts before the first accepted solution for that problem count.

Submissions after acceptance do not affect the solved problem's penalty.

### Ranking rules

1. Higher number of solved problems ranks first.
2. Lower total penalty ranks first.
3. Earlier last accepted submission timestamp ranks first.
4. Stable final tie-breaker: ascending participant ID.

Requirements:

- SCR-001 [Must]: Scoring shall be calculated on the backend.
- SCR-002 [Must]: Each problem shall contribute at most one solved result per participant.
- SCR-003 [Must]: Only the first accepted solution shall establish the problem's accepted timestamp.
- SCR-004 [Must]: Wrong attempts shall be counted according to the defined verdict policy.
- SCR-005 [Must]: Compilation and system errors shall not add penalty.
- SCR-006 [Must]: Penalty minutes shall be floored.
- SCR-007 [Must]: Ranking shall use the specified tie-breaking order.
- SCR-008 [Must]: Repeated judge callbacks shall not duplicate penalty.
- SCR-009 [Must]: Leaderboard projections shall be recalculable from canonical scoring records.

## 4.8 Submission deadline and finalization

The submission cutoff shall be based on the database transaction's server-side receipt time.

A submission is eligible if:

1. The API receives the submission before `end_time`.
2. The request passes authorization and validation.
3. The submission record and its durable job-outbox record are committed successfully before the cutoff.

Judging may finish after the contest ends.

Requirements:

- SUB-001 [Must]: The submission endpoint shall enforce the cutoff using server time.
- SUB-002 [Must]: A submission durably committed before the cutoff shall remain eligible.
- SUB-003 [Must]: A submission received at or after the cutoff shall be rejected.
- SUB-004 [Must]: Submission creation shall be idempotent.
- SUB-005 [Must]: Every submission shall have a unique internal identifier.
- SUB-006 [Must]: Every accepted submission shall have a durable judging job.
- SUB-007 [Must]: The final leaderboard shall wait for all eligible judging jobs to reach terminal states.
- SUB-008 [Must]: System failures shall be resolved through controlled retries or explicit incident handling before finalization.
- SUB-009 [Must]: The platform shall preserve submission receipt timestamps.

## 4.9 Hybrid proctoring

### Proctoring modes

1. Browser monitoring.
2. Browser + webcam.
3. Browser + webcam + screen monitoring.

Organizers may choose the required mode per contest.

### Consent and entry

- PROC-001 [Must]: The platform shall present a clear proctoring notice before requesting permissions.
- PROC-002 [Must]: Explicit consent shall be recorded before webcam or screen evidence collection.
- PROC-003 [Must]: Consent records shall include policy version and timestamp.
- PROC-004 [Must]: The participant shall be able to review the proctoring requirements before contest entry.
- PROC-005 [Must]: Mandatory-proctoring contests shall require the necessary permissions.
- PROC-006 [Must]: Participants shall be shown the current monitoring status.
- PROC-007 [Must]: The platform shall provide an accommodations and exception-request process.
- PROC-008 [Must]: Identity verification through ID photo and manual review is excluded from V1.

### Browser monitoring

Events:

- Tab visibility changes.
- Window focus loss.
- Window focus regain.
- Full-screen exit.
- Full-screen entry.
- Copy.
- Paste.
- Context-menu invocation.
- Page refresh.
- Browser disconnect.
- Session reconnection.

Important interpretation:

Copy/paste inside the coding editor is normal programming behavior and shall not automatically be classified as misconduct.

Browser events are client-reported and therefore forgeable.

The system shall treat them as investigative indicators, not verified facts.

Requirements:

- PROC-010 [Must]: Browser events shall include event type, session ID and client timestamp.
- PROC-011 [Must]: Events shall be deduplicated.
- PROC-012 [Must]: Repeated focus events shall use cooldown rules.
- PROC-013 [Must]: The backend shall use session heartbeats as the authoritative connectivity signal.
- PROC-014 [Must]: Missing heartbeats shall trigger a disconnect-status transition after a configured timeout.
- PROC-015 [Must]: Browser events shall not independently trigger automatic disqualification.

### Webcam monitoring

V1 capabilities:

- Webcam permission verification.
- Face presence detection.
- Multiple-face indicators.
- Prolonged absence indicators.
- Timestamped detection events.

Implementation:

- Webcam frames shall be sampled locally for detection.
- Raw continuous webcam video shall not be uploaded.
- Raw webcam recording is excluded from V1.
- Automated face detection shall not be used as definitive identity verification.
- Face-detection failures shall be treated cautiously because lighting, camera quality and accessibility conditions can affect accuracy.

Requirements:

- PROC-020 [Must]: Webcam permission status shall be checked before entry.
- PROC-021 [Must]: Face detection shall operate on sampled frames.
- PROC-022 [Must]: Face presence events shall be recorded with timestamps.
- PROC-023 [Must]: Multiple-face events shall be recorded as review indicators.
- PROC-024 [Must]: The system shall not automatically disqualify a participant based on face detection.

### Screen monitoring

V1 uses periodic screenshots rather than continuous screen recordings.

Requirements:

- PROC-030 [Must]: Screen monitoring shall use browser-supported display capture APIs.
- PROC-031 [Must]: Participants shall explicitly choose and authorize a display surface.
- PROC-032 [Must]: The system shall record the reported display surface type when supported.
- PROC-033 [Must]: A tab-only share shall be distinguished from a full-monitor share where browser metadata permits.
- PROC-034 [Must]: The system shall generate an event when screen sharing stops.
- PROC-035 [Must]: Screen capture shall stop when the contest session terminates.
- PROC-036 [Must]: Screenshots shall be captured every 60 seconds when enabled.
- PROC-037 [Must]: Screenshots shall be resized to a maximum of 640 × 360 pixels.
- PROC-038 [Must]: JPEG quality and image-size limits shall be applied.
- PROC-039 [Must]: Each screenshot shall be associated with a session and timestamp.
- PROC-040 [Must]: Screenshots shall be stored in private object storage.
- PROC-041 [Must]: Failed screenshot uploads shall not silently disappear; they shall be retried within a bounded policy.

### Evidence sizing

For a two-hour contest:

- 120 screenshots per participant.
- 500 participants.
- 60,000 screenshots maximum.
- Maximum target image size: 100 KB.

Estimated upper-bound storage:

`60,000 × 100 KB ≈ 6 GB per contest`

This estimate excludes metadata, replicas and storage overhead.

The production environment shall validate storage throughput and lifecycle policies before enabling screenshots for all 500 participants.

### Suspicion scoring

Example initial weights:

| Event | Weight |
|---|---:|
| Tab visibility loss | 5 |
| Full-screen exit | 5 |
| Multiple-face indicator | 20 |
| Prolonged face absence | 15 |
| Screen-sharing interruption | 10 |
| Repeated suspicious event pattern | Configurable |

Rules:

- PROC-050 [Must]: Scores shall be calculated server-side.
- PROC-051 [Must]: Duplicate events shall not repeatedly increase the score.
- PROC-052 [Must]: Tab-switch events shall have a 30-second per-session cooldown for score contribution.
- PROC-053 [Must]: Copy/paste events shall be logged but shall not automatically increase the suspicion score.
- PROC-054 [Must]: The total suspicion score shall be capped at 100.
- PROC-055 [Must]: Event severity and score shall be configurable.
- PROC-056 [Must]: Proctoring events shall be reviewable independently of the score.
- PROC-057 [Must]: Suspicion scores shall not automatically disqualify participants.

### Proctor review and disciplinary actions

- PROC-060 [Must]: Organizers shall assign proctors to contests.
- PROC-061 [Must]: Proctors shall view assigned participants.
- PROC-062 [Must]: Proctors shall review event timelines and authorized evidence.
- PROC-063 [Must]: Proctors shall add remarks.
- PROC-064 [Must]: Proctors may recommend disciplinary action.
- PROC-065 [Must]: Only ORGANIZER, ADMIN or SUPER_ADMIN with explicit contest authority may issue final disqualification.
- PROC-066 [Must]: Every disqualification shall require a reason.
- PROC-067 [Must]: Disciplinary decisions shall be auditable.
- PROC-068 [Must]: Participants shall have access to an appeal process.

## 4.10 Code similarity and plagiarism

V1 does not include automated plagiarism detection.

However:

- INT-001 [Should]: The database shall retain submissions in a format suitable for post-contest analysis.
- INT-002 [Should]: The architecture shall allow an independent plagiarism-analysis worker to be introduced.
- INT-003 [Should]: Similarity reports shall compare code after normalization.
- INT-004 [Should]: Similarity shall be treated as an investigation indicator, not proof of cheating.

---

# 5. Notifications and communication

- NOT-001 [Must]: The platform shall provide in-app notifications.
- NOT-002 [Must]: Email verification shall use an SMTP-compatible provider.
- NOT-003 [Must]: The platform shall support registration confirmation emails.
- NOT-004 [Must]: The platform shall support contest reminders.
- NOT-005 [Must]: Organizers shall publish contest announcements.
- NOT-006 [Must]: Participants shall receive relevant submission and result notifications.
- NOT-007 [Must]: Notification delivery failures shall not affect contest scoring.
- NOT-008 [Must]: Notification jobs shall be processed asynchronously.

---

# 6. Non-functional requirements

## 6.1 Performance

| Operation | Target |
|---|---|
| Normal API latency | P95 under 500 ms |
| Submission acknowledgement | P95 under 1 second |
| Draft autosave acknowledgement | P95 under 1 second |
| Leaderboard propagation | Within 3 seconds after scoring |
| Proctor event ingestion | P95 under 1 second |
| WebSocket reconnect | Within 5 seconds under normal network conditions |

## 6.2 Scalability

- NFR-001 [Must]: The application shall support 500 concurrent authenticated participants.
- NFR-002 [Must]: The platform shall support 500 simultaneous contest sessions.
- NFR-003 [Must]: The platform shall support 500 WebSocket connections.
- NFR-004 [Must]: API instances shall be horizontally scalable.
- NFR-005 [Must]: Judge workers shall scale independently.
- NFR-006 [Must]: Proctoring workers shall scale independently.
- NFR-007 [Must]: Submission bursts shall be absorbed through asynchronous queues.

### Judging throughput target

Benchmark scenario: `200 submissions × 30 test cases = 6,000 test executions`

- NFR-010 [Must]: The judging infrastructure shall demonstrate 25 completed test executions per second sustained under representative workload.
- NFR-011 [Must]: The infrastructure shall demonstrate a short burst target of 50 executions per second.
- NFR-012 [Must]: The platform shall support a benchmark of 6,000 test executions completing within approximately four minutes under target workload.
- NFR-013 [Must]: Judge capacity shall be benchmarked using representative C++, Python and Java programs.
- NFR-014 [Must]: The system shall support Judge0 batch submission where appropriate.
- NFR-015 [Must]: Judge callbacks shall be used where supported and configured.
- NFR-016 [Must]: Bounded polling shall be available as a fallback.
- NFR-017 [Must]: Judging throughput and queue wait time shall be monitored separately.

## 6.3 Availability and recovery

- NFR-020 [Must]: Target monthly platform availability shall be 99.5%.
- NFR-021 [Must]: Target contest-window application availability shall be 99.9%.
- NFR-022 [Must]: Database RPO shall target five minutes or less with PITR.
- NFR-023 [Must]: Database RTO shall target 60 minutes or less.
- NFR-024 [Must]: Acknowledged submissions shall be recoverable from durable database records.
- NFR-025 [Must]: The system shall support reconnection without resetting contest timing.
- NFR-026 [Must]: Redis failure shall not cause permanent loss of accepted submissions.

---

# 7. Architecture and Standards

- Modular monolith FastAPI backend with Celery workers.
- PostgreSQL as single source of truth; transactional outbox for event dispatch.
- Redis for queues, pub/sub and rate limiting.
- Next.js frontend with Monaco Editor.
- Private S3-compatible storage for screenshots with presigned URLs.
- Mandatory single-leader scheduler using PostgreSQL advisory locks.

---

# 8. Mandatory Implementation Constraints

1. Never execute participant code inside the FastAPI process.
2. Never expose hidden test cases through participant-facing APIs.
3. Never trust frontend clocks for contest timing.
4. Never allow Redis to be the sole source of truth for submissions.
5. Never score the same accepted submission twice.
6. Never treat Judge0 infrastructure failures as wrong answers.
7. Never automatically disqualify participants using suspicion scores.
8. Never allow a proctor to make an unauthorized final disciplinary decision.
9. Never expose evidence through public object-storage URLs.
10. Never modify a problem version used by a historical or live contest.
11. Never accept submissions after the authoritative cutoff.
12. Never publish final standings before eligible judging jobs are resolved.
13. Never assume that browser-based monitoring detects all external devices.
14. Never claim 500-participant production readiness without benchmark evidence.
15. Never deploy mandatory proctoring without an explicit consent and accommodation process.
