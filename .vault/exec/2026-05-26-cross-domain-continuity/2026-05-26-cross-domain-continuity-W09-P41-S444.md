---
tags:
  - '#exec'
  - '#cross-domain-continuity'
date: '2026-07-11'
modified: '2026-07-11'
body_hash: 'sha256:39be16f65261511ad275859c28a8e7d953b35c9c7e53a710a3d2b890309c0efe'
step_id: 'S444'
related:
  - "[[2026-05-26-cross-domain-continuity-plan]]"
---

# Add a real prorrata rollup regression proving Article 20 domestic-exempt volume enters the denominator only, and assert no current Modelo 303 casilla-61 binding or compatibility route is authored

## Scope

- `src/aeat/application/calculations/tests/test_prorrata_regularizacion.py src/aeat/_data/registry/aeat/modelos/303/`

## Description

- Exercise the real prorrata ledger rollup with a taxable baseline and a generic
  `DOMESTIC_EXEMPT` repercutido observation that carries no sub-article marker.
- Prove the exempt observation adds its full base only to total and
  without-deduction volume, leaving the deductible numerator unchanged.
- Load the shipped 2009-y-siguientes and 2023-y-siguientes Modelo 303 snapshots
  and prove casilla `61` has neither a canonical declaration, a noncanonical
  compatibility target, nor a casilla-61 binding identifier.

## Outcome

The accepted Article 20 correction is now protected by direct calculation and
registry behavior. No production calculation logic, registry data, casilla-61
compatibility contract, or casilla-83 abstraction was introduced.

Focused verification passed:

- `uv run --no-sync ruff check src/aeat/application/calculations/tests/test_prorrata_regularizacion.py`
- `uv run --no-sync pytest -q src/aeat/application/calculations/tests/test_prorrata_regularizacion.py` (`16 passed`)

## Notes

The completed S355 correction already had an unstaged, adjacent test hunk in
the shared worktree. It was preserved without modification; this record covers
only the new S444 regression and real-registry assertions.

## Final feature-surface gate

- `uv run --no-sync ruff check` on the seven S343/S355 production modules passed.
- The six owned deadline, CLI, IVA-domain, and prorrata test modules passed with
  `28 passed`.
- `vaultspec-core vault check all --feature cross-domain-continuity` exited zero:
  structure, frontmatter, links, placeholders, schema, and ADR status are clean.
  Its warnings are the pre-existing cross-domain modified-stamp, annotation, and
  markdown backlog, a feature-index count changed by the new phase summary, and
  an older unreferenced research record; none is a safety failure in this slice.
