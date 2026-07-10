---
tags:
  - '#research'
  - '#arch-remediation-ports-inversion'
date: '2026-07-06'
modified: '2026-07-08'
related:
  - "[[2026-07-02-arch-remediation-ports-inversion-adr]]"
  - "[[2026-07-02-arch-remediation-program-adr]]"
  - "[[2026-07-02-aeat-architecture-review-audit]]"
---

# `arch-remediation-ports-inversion` research: `program-track decision research bridge`

This research bridges the accepted ports-inversion ADR to the domain-boundary
audit and program-track evidence that motivated it. It is a vault lifecycle
record only: it does not change repository placement or dependency-injection
contracts.

## Findings

### Decision input

The domain-boundary audit had accepted existing domain-co-located encrypted
repositories as debt to migrate opportunistically. The architecture review
showed that mode did not close the seam: only fincas had migrated while many
domains still imported persistence adapters, and the layered ledger carried a
large waiver set.

The accepted ADR changed the migration mode from opportunistic to planned and
made the fincas layout the mandatory template. It chose per-domain campaigns
with gate-ledger burn-down rather than one large shared-worktree migration.

### Accepted constraints

Each domain migration is atomic: port declaration, concrete relocation,
consumer updates, `__all__` updates, import-linter ledger deletion, and
roundtrip gates land together with no re-export bridges. Single-writer and
encrypted-boundary equality contracts must not change.

### Current closure evidence

The arch-remediation program refresh records every track plan complete; the
ports-inversion plan reports 20 of 20 steps closed by `vaultspec-core vault
plan status`. The ADR's post-close honesty section records zero production
domain-to-adapters import coupling after static and dynamic follow-ups.

### Recommendation

Keep this research bridge as the evidence node for the accepted ADR. Future
repository relocation work should cite this decision and preserve the
per-domain atomic migration contract.
