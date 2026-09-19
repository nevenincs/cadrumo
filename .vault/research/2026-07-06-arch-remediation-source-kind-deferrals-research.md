---
tags:
  - '#research'
  - '#arch-remediation-source-kind-deferrals'
date: '2026-07-06'
modified: '2026-07-17'
body_hash: 'sha256:82bcf06376b1c0e8a204280c137947ab515f1b9cd3ceba1380e1796b46413ae1'
related:
  - "[[2026-07-02-arch-remediation-source-kind-deferrals-adr]]"
  - "[[2026-07-02-arch-remediation-program-adr]]"
  - "[[2026-07-02-aeat-architecture-review-audit]]"
---

# `arch-remediation-source-kind-deferrals` research: `program-track decision research bridge`

This research bridges the accepted source-kind-deferrals ADR to the
architecture-review register and program-track evidence that motivated it. It is
a vault lifecycle record only: it does not promote a source kind, add a
resolver, or change advisory behavior.

## Findings

### Decision input

The architecture-review register required each deferred source kind to either
gain a live resolver or be re-ratified with a target condition, and required the
reserved tier to stay explicitly tracked. The deferred set mixed IVA kinds with
accepted promotion dependencies and informativa detail-row kinds with no
grounded resolver design.

The accepted ADR chose per-kind re-ratification with typed target conditions.
It rejected promoting everything immediately because that would invent legal
behavior or ship hollow resolvers, and rejected comment-only deferrals because
the program requires deferral-as-data.

### Accepted constraints

The two IVA regularisation kinds promote only when their named dependencies are
proven. The informativa detail-row kinds remain deferred until a modelo
hardening campaign or concrete operator filing need triggers a grounded design
ADR. Deferred-source advisories must not be muted, and reserved kinds cannot be
consumed without promotion under the mesh ownership contract.

### Current closure evidence

The arch-remediation program refresh records every track plan complete; the
source-kind-deferrals plan reports 9 of 9 steps closed by `vaultspec-core vault
plan status`. The current program audit also records that future deferred
source-kind promotions still require trigger evidence and accepted design
authority.

### Recommendation

Keep this research bridge as the evidence node for the accepted ADR. Future
source-kind work should not treat the completed plan as permission to promote a
kind; promotion still requires the kind's trigger evidence and design authority.
