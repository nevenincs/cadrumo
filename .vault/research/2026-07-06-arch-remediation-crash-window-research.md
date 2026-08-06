---
tags:
  - '#research'
  - '#arch-remediation-crash-window'
date: '2026-07-06'
modified: '2026-07-17'
body_hash: 'sha256:593edf04a634bc5d8124a73c88f85d3b99db9aa4cf771a80e13f2be789ba6e8c'
related:
  - "[[2026-07-02-arch-remediation-crash-window-adr]]"
  - "[[2026-07-02-arch-remediation-program-adr]]"
  - "[[2026-07-02-aeat-architecture-review-audit]]"
---

# `arch-remediation-crash-window` research: `program-track decision research bridge`

This research bridges the accepted crash-window ADR to the architecture-review
finding and program-track evidence that motivated it. It is a vault lifecycle
record only: it does not add crash-window scope, alter persistence policy, or
create a new implementation wave.

## Findings

### Decision input

The architecture review identified the multi-store bucket state surface as
convention-guarded rather than test-proven. Single writes were atomic, but
composed verbs crossed the plaintext manifest, encrypted SQLite files, blob
store, and wrapped-key material without an audited crash-window matrix.

The accepted ADR chose HEAD-confirmed crash-injection coverage over a
documentation-only matrix. It explicitly rejected redesigning the storage
substrate and confined the work to verifying the existing composed-verb
orderings with real adapters and repair or diagnostic surfaces.

### Accepted constraints

The ADR froze the implementation scope to persistence storage adapter tests and
the grounding reference body. It required real encrypted SQLite, real blob-store
and keystore behavior, and anti-tautology crash injection rather than patching
the primitives under test. Production gaps surfaced by the tests were to be
reported honestly, not silently fixed under the test-only campaign.

### Current closure evidence

The arch-remediation program refresh records every track plan complete; the
crash-window plan reports 16 of 16 steps closed by `vaultspec-core vault plan
status`. The program ratchet bundle is green at current HEAD, so there is no
current code-gate blocker attached to this track.

### Recommendation

Keep this research bridge as the evidence node for the accepted ADR. Future
crash-window work should supersede or amend the ADR only if it changes
persistence policy, adds a new repair class, or changes the accepted
crash-injection surface.
