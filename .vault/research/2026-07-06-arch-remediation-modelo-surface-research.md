---
tags:
  - '#research'
  - '#arch-remediation-modelo-surface'
date: '2026-07-06'
modified: '2026-07-08'
related:
  - "[[2026-07-02-arch-remediation-modelo-surface-adr]]"
  - "[[2026-07-02-arch-remediation-program-adr]]"
  - "[[2026-07-02-aeat-architecture-review-audit]]"
---

# `arch-remediation-modelo-surface` research: `program-track decision research bridge`

This research bridges the accepted modelo-surface ADR to the architecture-review
finding and program-track evidence that motivated it. It is a vault lifecycle
record only: it does not create a new extension surface or change calculation
semantics.

## Findings

### Decision input

The architecture review found per-modelo special cases accreting inside generic
formula, validator, and orchestrator layers. Individual carve-outs were often
ADR-grounded, but the aggregate effect was that hardening one modelo required
editing contended generic hub files and preserving implicit cross-layer
contracts such as sentinel Decimal values.

The accepted ADR chose typed outcomes, registry-declared data, named
per-modelo modules, and a ratchet gate. It rejected both status quo and generic
plugin classes because the measured carve-outs were mostly values and sets, not
open-ended behavior.

### Accepted constraints

Semantics are frozen: aggregation-taxonomy rulings, iva-wallet ownership,
lock/carry override behavior, and `CasillaObservation` provenance must survive
representation changes. No legacy sentinel channel may coexist with the typed
outcome, and registry-authority-flow governs relocated data.

### Current closure evidence

The arch-remediation program refresh records every track plan complete; the
modelo-surface plan reports 21 of 21 steps closed by `vaultspec-core vault plan
status`. The current ratchet bundle is green at HEAD.

### Recommendation

Keep this research bridge as the evidence node for the accepted ADR. Future
modelo-specific behavior in generic modules should be routed through the
declared surfaces or explicitly adjudicated by a superseding decision.
