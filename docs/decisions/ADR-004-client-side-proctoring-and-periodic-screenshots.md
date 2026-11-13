# ADR-004: Client-Side Hybrid Proctoring and Periodic Screenshots

## Status
Accepted

## Date
2026-11-13

## Context
Contest integrity requires proctoring monitoring without compromising participant privacy, overloading network bandwidth, or incurring astronomical video storage costs.
Key factors:
- 500 concurrent participants streaming continuous webcam and screen video would require ~1.5 Gbps sustained uplink and hundreds of gigabytes per hour.
- Continuous video recording creates severe privacy and regulatory exposure under GDPR and India's DPDP Act 2023.
- Automated AI disqualification introduces high risks of false positives due to lighting and hardware variance.

## Decision
Adopt a **Hybrid Proctoring Model** combining client-side analysis and periodic downscaled screenshots:

1. **Client-Side Face Detection**: Sample webcam frames locally in browser memory (WebAssembly/MediaPipe); upload only timestamped detection events (`WEBCAM_FACE_PRESENT`, `WEBCAM_MULTIPLE_FACES`, `WEBCAM_FACE_ABSENT`). No raw continuous webcam video is transmitted or saved.
2. **Periodic Screen Screenshots**: Capture screens every 60 seconds; downscale on an HTML5 canvas to a maximum of 640 × 360 JPEG (<100 KB); upload directly to private S3 via presigned URLs.
3. **Browser Event Tracking**: Monitor tab focus, full-screen status, and clipboard events with a 30-second score cooldown.
4. **Human-in-the-Loop Disciplinary Governance**: Algorithmic suspicion scores serve strictly as investigative indicators. Only authorized human organizers or admins can issue disqualifications with recorded reasons.
5. **Strict 7-Day Screenshot Retention**: Automated lifecycle rules delete screenshots after 7 days unless preserved for active appeals.

## Alternatives Considered

### Continuous Full-Motion WebRTC Video Streaming & Archival
- *Pros*: Complete visual record of the participant.
- *Cons*: Prohibitive server bandwidth, extreme storage cost (~300 GB+ per contest), invasive privacy posture, potential regulatory violation.
- *Rejected*: Disproportionate and unfeasible for 500 concurrent participants in V1.

### Automatic Disqualification via Computer Vision
- *Pros*: Zero human proctor staffing required.
- *Cons*: High false-positive rate from lighting shifts, glasses, or camera position; creates severe participant unfairness.
- *Rejected*: Violates core product ethics and contest integrity rules.

## Consequences
- Reduces storage budget from >300 GB down to ~6 GB per 2-hour contest.
- Protects participant privacy and ensures DPDP/GDPR compliance.
- Ensures fair adjudication through mandatory human review.
