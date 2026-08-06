---
tags:
  - '#research'
  - '#arch-remediation-program'
date: '2026-07-06'
modified: '2026-07-17'
body_hash: 'sha256:48ad5b215ecca1c155da5409c195d6e66d4b26f312b0df5760a12a196c5bf527'
related:
  - "[[2026-07-02-aeat-architecture-review-audit]]"
  - "[[2026-07-02-arch-remediation-program-adr]]"
  - "[[2026-07-06-arch-remediation-program-audit]]"
---

# `arch-remediation-program` research: `program decision research bridge`

This research bridges the accepted `arch-remediation-program` ADR to the audit
evidence that motivated it and to the current closure refresh. It is a
curation record for vault lifecycle health: it does not introduce a new wave,
change the accepted ordering, or alter any ratchet ceiling.

## Findings

### Decision input

The 2026-07-02 architecture review found the bindings and cross-period
framework architecturally sound but carrying concurrent partial consolidation
campaigns and a broken measurement surface. Its deferral register identified
the gates-ratchet instrument work, bindings-campaign tails, source-kind
deferrals, registry-format convergence, lazy-import policy, data budget, and
related structural fan-out as ordered remediation work rather than independent
cleanup.

The accepted program ADR converted that audit into a wave order:
instruments first, bindings tails next, core decisions before fan-out, and a
fresh-context closure review. Its small-plan topology was chosen because the
vault's large epic history made a single L4 remediation epic too easy to stall
or bury for new-context agents.

### Accepted constraints

The program ADR binds the following constraints:

- Wave 0 repairs the `.importlinter` measurement instrument before other
  remediation is measured against it.
- Wave 1 drains the three bindings tail plans without cutting a new plan and
  freezes new source kinds and resolver conventions until closure.
- Wave 2 accepts the core shape decisions before implementation fan-out.
- Wave 3 fans out track plans only after the relevant decisions are accepted.
- Wave 4 requires a fresh-context honesty review and ratchet verification.
- Ratchets may be loosened only by an accepted ADR.

These constraints remain the program authority. This research record only
documents why the accepted ADR exists and how current closure evidence relates
to it.

### Current status evidence

The 2026-07-06 program audit refresh records that the prior red ratchet finding
is stale at current HEAD: the Wave 4 ratchet bundle now passes 38 tests. It
also records that the three D9 plans and all nine arch-remediation track plans
remain structurally complete by `vaultspec-core vault plan status`, and that an
open-row grep over `.vault/plan` finds no unchecked plan rows.

The remaining live issues are not implementation gaps inside the program's code
tracks:

- `arch-remediation-gates-ratchet` has a plan but no same-feature ADR. A
  separate research bridge now grounds the recommended curation ADR; creating
  that ADR still requires explicit ADR approval.
- `just release-readiness` is blocked by GitHub issue `#116`, the permanent
  live-AEAT-write safety charter currently labelled `priority:P0-blocker`. The
  release-readiness gate intentionally treats such an issue as a hard block.

### Recommendation

Keep this record as the research bridge for the accepted program ADR. Future
work should not reopen the wave order unless a superseding ADR is explicitly
approved. The remaining same-feature warning belongs to the
`arch-remediation-gates-ratchet` feature, not this parent program feature, and
the release-readiness blocker belongs to release-policy ownership rather than
program implementation.
