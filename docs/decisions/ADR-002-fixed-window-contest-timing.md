# ADR-002: Fixed-Window Contest Timing Model

## Status
Accepted

## Date
2026-11-13

## Context
Contest platforms typically choose between two timing models:
1. **Dynamic / Individual Window**: Each participant gets a fixed duration (e.g. 2 hours) starting from the instant they click "Start Contest", allowing asynchronous start times.
2. **Fixed-Window**: All participants share identical, synchronized contest start and end timestamps.

Key constraints:
- Real-time leaderboard competition and public score freezing.
- Proctoring verification across simultaneous participants.
- Prevention of client clock manipulation.

## Decision
Implement a **Fixed-Window Contest Model** for all V1 contests.

- **Authoritative Server Clocks**: Contest start (`start_time`) and end (`end_time`) timestamps are enforced strictly on the server.
- **Derived Duration**: The contest does not store an independent `duration` column; duration is always derived: `end_time - start_time`.
- **Late Joining Policy**: Participants who join late receive only the remaining time until `end_time`. No compensatory time is awarded.
- **Strict Submission Cutoff**: Submissions received at or after `end_time` are rejected immediately with HTTP 400 (`CONTEST_ENDED`).

## Alternatives Considered

### Individual / Asynchronous Timing Windows
- *Pros*: Greater convenience for participants across time zones.
- *Cons*: Prevents synchronous leaderboard freezing, increases cheating risk (earlier finishers leaking problems to later participants), and complicates synchronized proctor monitoring.
- *Rejected*: Incompatible with ICPC-style synchronized competitive integrity in V1.

## Consequences
- Preserves ICPC integrity: all contestants compete on the exact same timeline.
- Simplifies leaderboard freeze mechanics and live contest proctoring.
- Requires reliable time synchronization (NTP) on backend application servers.
