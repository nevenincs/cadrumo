---
generated: true
tags:
  - '#index'
  - '#arch-remediation-engine-lifecycle'
date: '2026-08-16'
modified: '2026-08-26'
body_schema: 'body-v1'
body_hash: 'sha256:d08e8e053c88485214a49b4b68dea64a191461ccd45dad1b50339f8639fd7445'
related:
  - '[[2026-07-02-arch-remediation-engine-lifecycle-adr]]'
  - '[[2026-07-02-arch-remediation-engine-lifecycle-plan]]'
  - '[[2026-07-04-arch-remediation-engine-lifecycle-audit]]'
  - '[[2026-07-06-arch-remediation-engine-lifecycle-research]]'
---

# `arch-remediation-engine-lifecycle` feature index

Auto-generated index of all documents tagged with `#arch-remediation-engine-lifecycle`.

## Documents

### adr

- `2026-07-02-arch-remediation-engine-lifecycle-adr` - `arch-remediation-engine-lifecycle` adr: `engine and bucket-session lifecycle unification` | (**status:** `accepted`)

### audit

- `2026-07-04-arch-remediation-engine-lifecycle-audit` - `arch-remediation-engine-lifecycle` audit: `campaign close honesty review`

### exec

- `2026-07-02-arch-remediation-engine-lifecycle-P01-S01` - Make the bucket-session manager acquire the bucket engine lazily on first storage access within a session, registering the engine handle on the session
- `2026-07-02-arch-remediation-engine-lifecycle-P01-S02` - Dispose the bucket engine on session close and on profile switch through the same path that invalidates session state, so the two lifecycles cannot diverge
- `2026-07-02-arch-remediation-engine-lifecycle-P01-S03` - Re-key the engine cache on bucket identity rather than raw database URL, keeping the URL an implementation detail of engine construction
- `2026-07-02-arch-remediation-engine-lifecycle-P01-S04` - Narrow dispose_engine to an internal seam invoked by the session owner and the harness teardown only
- `2026-07-02-arch-remediation-engine-lifecycle-P01-S05` - Confirm the settings-driven explicit-database-URL route keeps its current direct engine path unchanged
- `2026-07-02-arch-remediation-engine-lifecycle-P02-S06` - Sweep the shared secure-SQL harness ephemeral and synthetic-session path onto the unified lifecycle so engine routing follows the session through the harness teardown
- `2026-07-02-arch-remediation-engine-lifecycle-P02-S07` - Confirm the harness synthetic-session roundtrip suites pass against the unified lifecycle
- `2026-07-02-arch-remediation-engine-lifecycle-P03-S08` - Add a regression asserting an in-process profile switch cannot observe the prior bucket engine, via an engine-identity assertion across a switch
- `2026-07-02-arch-remediation-engine-lifecycle-P03-S09` - Add a regression asserting closing a session disposes its engine, verified by pool inspection
- `2026-07-02-arch-remediation-engine-lifecycle-P03-S10` - Delete the now-unnecessary scattered dispose_engine calls from the CLI lifecycle, rename, and navigation tests whose choreography the unified lifecycle makes redundant
- `2026-07-02-arch-remediation-engine-lifecycle-P03-S11` - Confirm the existing session-lifecycle and profile-navigation suites pass with the scattered disposals removed and the use-time readiness guards untouched

### plan

- `2026-07-02-arch-remediation-engine-lifecycle-plan` - `arch-remediation-engine-lifecycle` plan

### research

- `2026-07-06-arch-remediation-engine-lifecycle-research` - `arch-remediation-engine-lifecycle` research: `program-track decision research bridge`
