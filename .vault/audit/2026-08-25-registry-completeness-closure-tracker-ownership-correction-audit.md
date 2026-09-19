---
tags:
  - '#audit'
  - '#registry-completeness-closure'
date: '2026-08-25'
modified: '2026-08-25'
body_schema: 'body-v1'
body_hash: 'sha256:0c93e923adb340b0959a1e856f38830ece8fd04002dbf9c994bab01530e05856'
related:
  - '[[2026-08-14-registry-temporal-coverage-plan]]'
  - '[[2026-08-10-aeat-export-fragment-generator-authority-plan]]'
  - '[[2026-08-24-registry-completeness-closure-plan]]'
---
# `registry-completeness-closure` audit: superseded tracker ownership correction

## Scope

This post-archive curation audit corrects ownership language in the archived
`registry-suite-red-at-head` tracker reconciliation. It does not alter the
historical tracker, revive its retired umbrella rows, or claim that the
registry is green.

VaultSpec RAG discovery was used before adjudication to find the active plans
already carrying the same work and prevent redeclaration.

## Findings

### tracker-ownership | high | Archived umbrella rows are not current owners

The archived reconciliation incorrectly continued to describe retired
`P03.S22` and `P03.S23` as owners. Those rows were non-executable
close-the-world umbrellas and remain retired. Archival means the historical
tracker was reconciled and superseded; it never means the registry or its
release predicate is green.

### claimed-year-gate | high | Twelve divergences remain under exact live owners

The current claimed-year gate fails with twelve modelos: 126, 128, 165, 181,
184, 200, 270, 308, 309, 341, 353, and 576. This was reproduced with
`uv run --no-sync pytest -q -n 0 src/cadrumo/domain/calculations/registry/tests/test_layout_design_applies_to_claimed_years.py`:
one failed and nine passed. The eleven non-200 divergences are owned by
`registry-temporal-coverage` `W02.P05.S51`. Modelo 200 is owned by
`aeat-export-fragment-generator-authority` `W04.P08.S22` and `W04.P08.S34`.
No implementation work is orphaned, and reviving the old umbrella rows would
duplicate those active homes.

### release-predicate | high | Registry validation is green while completeness is red

`uv run --no-sync aeat app registry verify` passes for 58 modelos and 111
revisions. The stricter command
`uv run --no-sync python -m dev.registry.conformance closure --check --json`
exits non-zero: only one revision is satisfied and 110 are refused, principally
because source-connectivity evidence is unmeasured or missing. The open final
release-gate row in `registry-completeness-closure` therefore remains open.

### registry-tests | medium | Collection failure was stale consumer relocation

The registry test tree stopped during collection because three tests still
imported names from the intentionally inert `domain.user_profile` facade. The
consumers now import their canonical concrete modules, without restoring a
facade, and their focused three-file run passes 41 tests. This was consumer
convergence after a no-compatibility relocation, not a registry-validation
defect.

## Recommendations

- Treat the active temporal, export-authority, and completeness rows named
  above as the only implementation owners.
- Keep the archived tracker archived and cite this audit whenever its obsolete
  ownership wording is encountered.
- Keep the completeness plan open until its real closure predicate passes.
- Execute temporal `S51` as evidence-acquisition and source-era slices; never
  narrow legal selection spans or backdate later layouts merely to green its
  gate.
