---
tags:
  - '#research'
  - '#arch-remediation-lazy-import-policy'
date: '2026-07-06'
modified: '2026-07-08'
related:
  - "[[2026-07-02-arch-remediation-lazy-import-policy-adr]]"
  - "[[2026-07-02-arch-remediation-program-adr]]"
  - "[[2026-07-02-aeat-architecture-review-audit]]"
---

# `arch-remediation-lazy-import-policy` research: `program-track decision research bridge`

This research bridges the accepted lazy-import-policy ADR to the architecture
review and program-track evidence that motivated it. It is a vault lifecycle
record only: it does not add allowlist entries, change ratchet ceilings, or
alter import policy.

## Findings

### Decision input

The architecture review measured hundreds of production function-local imports.
Some were accepted lazy-loading or optional-dependency patterns; others hid
first-party cycles and softened layer boundaries at runtime while the static
import graph looked clean.

The accepted ADR chose a closed sanctioned-class taxonomy, a declared allowlist
for unsanctioned sites, per-class ratchets, and a runtime-graph cadence hook. It
rejected both no policy and a blanket ban on function-local imports because
accepted cold-start and resource-loader decisions already rely on sanctioned
laziness.

### Accepted constraints

Sanctioned classes are inherited from earlier accepted decisions:
core resource loaders, CLI/PEP 562 cold-start deferrals, `TYPE_CHECKING`,
optional third-party guards, and adapter-heavy third-party deferrals. New
first-party cycle-breaks or cross-layer softening require a declared allowlist
entry in the same change.

### Current closure evidence

The arch-remediation program refresh records every track plan complete; the
lazy-import-policy plan reports 6 of 6 steps closed by `vaultspec-core vault
plan status`. The current Wave 4 ratchet bundle includes the lazy-import policy
tests and passes 38 tests at HEAD.

### Recommendation

Keep this research bridge as the evidence node for the accepted ADR. Future
changes should only adjust the taxonomy, allowlist, or ratchet ceilings through
the policy's declared mechanisms and, where ceilings loosen, accepted ADR
authority.
