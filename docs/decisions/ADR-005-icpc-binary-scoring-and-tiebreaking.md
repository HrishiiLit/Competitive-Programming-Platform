# ADR-005: ICPC Binary Scoring and Deterministic Tie-Breaking Engine

## Status
Accepted

## Date
2026-11-13

## Context
Contest platforms support diverse scoring methodologies:
1. **ICPC All-or-Nothing Scoring**: Binary solved/unsolved per problem, time penalty calculation based on elapsed minutes from start plus fixed wrong-submission penalties.
2. **IOI Partial / Subtask Scoring**: Graded points based on passed test subtasks, grouping, and partial constraints.

The platform targets collegiate and professional competitive programming contests adhering to the international ICPC standard.

## Decision
Implement strict **ICPC Binary All-or-Nothing Scoring** with a deterministic 4-stage tie-breaking hierarchy:

1. **Scoring Model**: A problem is either solved (1) or unsolved (0). No partial points exist in V1.
2. **Penalty Formula**:
   $$\text{Problem Penalty} = \left\lfloor \frac{\text{accepted\_at} - \text{contest\_start\_time}}{60\text{ seconds}} \right\rfloor + (20 \times \text{qualifying\_incorrect\_attempts})$$
3. **Qualifying Attempts**: Only incorrect attempts (`WA`, `TLE`, `MLE`, `RTE`, `OLE`) submitted *before* the first accepted submission incur the 20-minute penalty.
4. **Zero-Penalty Verdicts**: `COMPILATION_ERROR` and `SYSTEM_ERROR` do not incur penalty.
5. **Deterministic Standings Order**:
   - Primary: Problems Solved (`DESC`)
   - Secondary: Total Penalty Minutes (`ASC`)
   - Tertiary: Timestamp of Last Solved Problem (`ASC`)
   - Quaternary: Participant User ID (`ASC`)

## Alternatives Considered

### IOI Partial Subtask Scoring
- *Pros*: Finer gradation between intermediate solutions.
- *Cons*: Substantially more complex judge aggregation, incompatible with standard ICPC rulesets, requires custom test grouping in Judge0.
- *Rejected*: Deferred to future V1.1/V2 roadmap.

## Consequences
- Clean, predictable leaderboards aligned with international collegiate standards.
- Low computation overhead for leaderboard re-projections upon submission resolution.
- Clear mental model for contestants.
