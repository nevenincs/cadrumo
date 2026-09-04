---
tags:
  - '#exec'
  - '#reachability-burndown'
date: '2026-09-04'
modified: '2026-09-04'
body_schema: 'body-v2'
body_hash: 'sha256:d972372833949e829983e881d2f961b0761a38010e67f643dc99af229ad58c74'
step_id: 'S10'
related:
  - "[[2026-09-04-reachability-burndown-plan]]"
---

# Resolve the application/modelo and adapters/persistence symbol concentrations

## Scope

- `src/cadrumo/application`

## Changes

- `M` `src/cadrumo/application/modelo/_calculation_preparation.py`
- `M` `src/cadrumo/application/modelo/_verification_predicates.py`
- `M` `dev/audit/reachability_classification.toml`
- `verify:` `uv run --no-sync pytest -q src/cadrumo/application/modelo/tests -k "calculation_prep or verification_predicate or predicate"` -> `pass`
- `verify:` `uv run --no-sync ty check src/cadrumo/application/modelo/_calculation_preparation.py src/cadrumo/application/modelo/_verification_predicates.py` -> `pass`

## Notes

Six module-level alias facades removed, taking the unused-symbol count from 1403 to 1397.
Each was verified individually before removal: one reference tree-wide, which was its own
assignment; absent from every `__all__`; and its private original still used three or more
times inside the defining module. Removing the alias therefore changed no behaviour, which
150 owning tests, ty, ruff and an import smoke confirm. The audit no longer reports any of
the six.

These came from the tree-wide sweep rather than from reading files: an AST scan for
module-level public-to-private assignment found 157 alias layers across the shipped
package, a construct the architecture boundaries forbid outright. Seventeen were
audit-flagged; six met all three removal conditions.

`did_page_required` was found by the same sweep and deliberately left alone. It is declared
in its module's `__all__`, so it is exported public API with no consumer rather than a dead
alias, and removing it would change the published surface. That is a different problem
needing its own decision.

## Notes on the shared tree

The module ratchet is RED in this worktree and it is not this campaign's breakage. Nine new
shipped modules arrived from concurrent work; the gate names two package roots,
`cadrumo.domain.contabilidad` and `cadrumo.domain.is_compensation`, landed across commits
9d53bbfd8c, 1130652f85 and 553805181d as new Modelo 200 accounting and IS compensacion
capability whose consumers are not written yet.

The gate is correct to be red and was deliberately left red. Its own message says each
finding is harness code to relocate or capability to delete and that it must not be
baselined to make it pass, and adding an `allowed` line is precisely the erosion this
campaign forbids. The right resolution belongs to whoever is landing that capability:
either wire it, or record it. Both packages are already classified `staged-capability` in
this campaign's ledger with their commits named, so the work is visible rather than
silenced.
