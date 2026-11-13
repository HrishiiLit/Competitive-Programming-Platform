# Security Policy

## Supported Versions

We release security updates and bug fixes for the current implementation baseline and actively supported releases.

| Version | Supported | Status |
|---|:---:|---|
| 1.1.x | ✅ | Current Implementation Baseline |
| 1.0.x | ❌ | Deprecated |
| < 1.0 | ❌ | Unsupported |

---

## Reporting a Vulnerability

We take the security of the **Competitive Programming Platform with Hybrid Proctoring** very seriously. If you discover a vulnerability, please do NOT create a public GitHub issue. Instead, follow our responsible disclosure process:

1. **Email Details**: Send an email to **`security@cpplatform.local`** (or contact the repository maintainers directly).
2. **Include Required Context**:
   - Type of vulnerability (e.g., Auth bypass, IDOR, Sandbox Escape, SQL Injection, SSRF).
   - Detailed step-by-step reproduction instructions or a minimal Proof of Concept (PoC).
   - Affected endpoints or components (e.g., `/api/v1/submissions`, Judge0 worker, S3 presigned URLs).
   - Potential impact on contest integrity or user privacy.
3. **Response Timelines**:
   - **Initial Acknowledgement**: Within **24–48 hours**.
   - **Triage & Assessment**: Within **72 hours**.
   - **Patch Release & Advisory**: Within **14 business days** for high/critical vulnerabilities.

---

## Security Invariants

When submitting bug reports or code reviews, note the following non-negotiable architectural invariants:

1. **No Participant Code in FastAPI**: User code must never execute within the API web service process; all execution is restricted to sandboxed Judge0 workers.
2. **Server Timestamps are Authoritative**: Client-reported clocks are never trusted for contest start, end, or submission cutoffs.
3. **Hidden Test Cases Stay Hidden**: Hidden test inputs and expected outputs must never be exposed through participant-facing REST or WebSocket payloads.
4. **No Automated Disqualification**: Algorithmic suspicion scores or face detection events must never trigger automated disqualification without human authorization.
5. **Private Evidence Storage**: Proctoring screenshots must reside in private S3 buckets and be accessible only via time-bounded presigned URLs.

For full technical specifications on our security model, STRIDE threat register, and RBAC matrix, please refer to [docs/security.md](docs/security.md).
