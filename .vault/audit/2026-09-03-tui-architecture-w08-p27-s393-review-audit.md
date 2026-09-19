---
tags:
  - '#audit'
  - '#tui-architecture'
date: '2026-09-03'
modified: '2026-09-03'
body_schema: 'body-v2'
body_hash: 'sha256:40e7190f1c3b0670919357624302631703926428e84434887849da58b4e62876'
related: []
---
# `tui-architecture` audit: `W08.P27.S393 Declarations calendar projection review`

## Scope

Independent review of the live S393 full Declarations calendar projection and tests. The review traced the legal schedule, local filing, AEAT evidence, and source-availability axes; known absence versus unobservable state; stale and known-empty handling; natural identity, ordering and duplicates; recovery-action authority; sensitive-data stripping; import direction and I/O; and adversarial test strength.

## Findings

### natural-calendar-addresses-are-normalized-or-orphaned-instead-of-refused | high | Closed: complete coordinates must agree and evidence must belong to the schedule

The initial projector silently normalized a calendar entry whose explicit filing year disagreed with its period year, and allowed a contradictory evidence address to become an orphan that changed source counts without changing a projected row.

Remediation validates every calendar entry's explicit filing year against its period before building the schedule address set. Evidence must be complete, its filing year must match its period year, and every evidence natural address must be present in that schedule set. Contradictions now fail before projection or counting. The expanded matrix covers calendar disagreement, local-evidence disagreement, AEAT-evidence disagreement, and a complete orphan address, in addition to partial addresses and existing axis mismatches. A positive exact-join test proves the matching evidence count and projected local/AEAT states agree. This finding is closed.

## Positive findings

The projection preserves schedule, local filing, and AEAT evidence as three total canonically ordered availability axes. Observable known `NOT_OBSERVED` remains distinct from unobservable AEAT state: the former emits the enum plus `justificante_verified=False`, while the latter emits `None` for both and an unknown count. Stale observations retain their time and values; known empty is zero while unavailable is unmeasured. Legal status and user state, window order, payment cutoff, AEAT justificante state, duplicate schedule identities, confident claims on unavailable axes, authority mismatches, recovery binding address, and unavailable schedules with rows all fail closed.

Rows sort deterministically by adjusted deadline and natural identity. Recovery actions are hidden from serialization and repr, pinned to the canonical create-action identity, and require the exact Modelo/year/period bindings. Protected work, revision, filing, snapshot, CSV, AEAT reference, event prose, names, URLs, and recovery identities are absent from serialized and repr output. The projector consumes prebuilt calendar and evidence values only; it imports no adapters, entrypoints, readers, filesystem or network facilities and performs no I/O.

## Verification

Initial gates: all 14 focused tests passed; Ruff and ty passed. Final re-probe inspected the exact entry-year, evidence-year, orphan-address guards and their expanded adversarial matrix, including the original two reproduced states. No open finding remains.

## Recommendation

CLOSE. The high natural-address and evidence-join coherence finding is closed. W08.P27.S393 is safe to mark complete.
