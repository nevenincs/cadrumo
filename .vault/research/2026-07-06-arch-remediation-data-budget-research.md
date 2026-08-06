---
tags:
  - '#research'
  - '#arch-remediation-data-budget'
date: '2026-07-06'
modified: '2026-07-22'
body_hash: 'sha256:af2bb0bced7dc9d4f78b460de759abc78a1703b56fb6a9dfa3cf5ffcd002a3e6'
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

## Supported-period hydration evidence

Reviewed on 2026-07-22. Because the live worktree contained unrelated peer work, the reviewer used a temporary alternate Git index based on `HEAD`. The index contained exactly 244 changed or staged feature-owned files and zero peer-owned paths. This isolated index provides the authoritative landing evidence for this feature.

The budget universe contained 18,396 indexed shipped-data files under `src/cadrumo/_data`, excluding every `tests/` subtree.

- Whole tree: 618,845,924 bytes, or 590.177464 mebibytes (MiB), against 625 MiB. Headroom: 34.822536 MiB.
- Runtime slice: 258,436,356 bytes, or 246.464115 MiB, against 270 MiB. Headroom: 23.535885 MiB.
- Aggregate corpus-binary slice: 360,409,568 bytes, or 343.713348 MiB, against 380 MiB. Headroom: 36.286652 MiB.

The landing real companion builds measured 80,329,080 bytes for `cadrumo-data-official` and 77,547,800 bytes for `cadrumo-data-manuals`. Both remained below the strict 100,000,000-byte cap. These are landing-rerun build results, not forecasts.

Current companion sizes do not require repartitioning. Repartitioning would change physical ownership without reducing the logical total.
