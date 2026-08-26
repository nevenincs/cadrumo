---
tags:
  - '#exec'
  - '#tui-architecture'
date: '2026-08-26'
modified: '2026-08-26'
body_schema: 'body-v2'
body_hash: 'sha256:80ef0c34ac8c6aee1cf6676b1694d1628006876690089ee8a89e889c26a969df'
step_id: 'S167'
related:
  - "[[2026-08-11-tui-architecture-plan]]"
  - "[[2026-08-24-tui-registry-api-gate-adr]]"
---

# Register in the public application/modelo/workspace_producers.py defining module exactly one application-owned S126 epoch-v2 port realization over each of the eight canonical native owner capture/current-coordinate surfaces, atomically relocate the existing field-manifest contract into that sole registration inventory, consume every native surface by direct defining-module import, and prove exact contributor identities, one native capture, contract-derived stamps, unchanged owner generations and comparison domains, admission-set coverage, same-domain validation, and refusal of missing, duplicate, stale, torn, ABA, cross-domain, or cross-incarnation coordinates without an alternate authority, shim, alias, fallback, re-export bridge, or adapter-package implementation

## Scope

- `src/cadrumo/application/modelo/workspace_producers.py and focused native-seam conformance/direct-import tests`

## Changes

- `M` `src/cadrumo/application/modelo/workspace_producers.py` (this commit; two earlier commits, `6c3319e804` and `907646f3af`, landed the first 5 contributors and the S274 fingerprint fix respectively)
- `M` `src/cadrumo/application/modelo/tests/test_workspace_producers.py`
- `verify:` `uv run --no-sync pytest src/cadrumo/application/modelo/tests/test_workspace_producers.py -m 'unit or integration' -q` -> `pass` (22 passed; 1 unrelated pre-existing failure, a gitignored local benchmark-snapshot stray file scan)

## Notes

Landed across three commits rather than one: `6c3319e804` registered the five
contributors whose native captures already fingerprinted cleanly (WORK,
READINESS, CLOSURE, LOCALE_CATALOGUE, FIELD_MANIFEST); `907646f3af` (S274)
corrected the fingerprint mechanism itself after discovering it refused every
Decimal-bearing model; this commit adds the three that needed that fix
(REGISTRY, BOUNDED_REVIEW, CALCULATION) and closes
`MODELO_WORKSPACE_PRODUCER_CONTRACT_INVENTORY_V1` over all eight.

Every owner/producer identity was corrected to reproduce
`2026-08-24-tui-registry-api-gate-adr.md`'s "contributor fixed point" table
verbatim -- the first pass (in `6c3319e804`) had invented plausible-looking
labels for the five contributors instead of reading that table, which a
dedicated test (`test_every_contract_matches_the_governing_adrs_contributor_fixed_point`)
now pins against the real production constants. REGISTRY needed a
discriminated envelope (`ModeloWorkspaceRegistryProjectionV1`) since its
native capture returns one of two admission-specific shapes
(`RegistryRevisionInspection` for static inspection, `RegistrySnapshot` for a
graded snapshot), never both -- proven by capturing both real admission
shapes and asserting the envelope refuses carrying both or neither.
