---
tags:
  - '#research'
  - '#arch-remediation-data-budget'
date: '2026-07-06'
modified: '2026-07-08'
related:
  - "[[2026-07-02-arch-remediation-data-budget-adr]]"
  - "[[2026-07-02-arch-remediation-program-adr]]"
  - "[[2026-07-02-aeat-architecture-review-audit]]"
---

# `arch-remediation-data-budget` research: `program-track decision research bridge`

This research bridges the accepted data-budget ADR to the architecture-review
finding and program-track evidence that motivated it. It is a vault lifecycle
record only: it does not change wheel contents, data budgets, or packaging
policy.

## Findings

### Decision input

The architecture review found bundled data growth was unbudgeted while the wheel
also shipped in-package tests and fixtures. The accepted corpus-packaging
decision remained load-bearing; the gap was that data growth and wheel payload
were invisible to gates.

The accepted ADR chose test/fixture exclusion from the wheel plus an executable
size-budget gate. It rejected immediate corpus splitting as premature and kept
that as the budget-breach escape hatch.

### Accepted constraints

The wheel remains functionally complete: `_data`, corpus, registry, terminology,
agent harness resources, `py.typed`, the BIP-39 wordlist, and
`external_constants.toml` stay packaged. The boundary is asserted after a real
wheel build, and budget raises require accepted ADR authority.

### Current closure evidence

The arch-remediation program refresh records every track plan complete; the
data-budget plan reports 5 of 5 steps closed by `vaultspec-core vault plan
status`. The current Wave 4 ratchet bundle includes data-size, codebase-size,
wheel-content, and bundled-corpus/registry checks and passes 38 tests at HEAD.

### Recommendation

Keep this research bridge as the evidence node for the accepted ADR. Future
work should use an ADR only for an actual budget raise, data-package split, or
wheel boundary change.
