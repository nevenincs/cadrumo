---
tags:
  - '#exec'
  - '#tui-architecture'
date: '2026-08-30'
modified: '2026-08-30'
body_schema: 'body-v2'
body_hash: 'sha256:ba1483451d634ddde688de0b3598e74619263c118a4bd3a752c523bcd9cdeade'
step_id: 'S322'
related:
  - "[[2026-08-11-tui-architecture-plan]]"
---

# Sever the remaining codebase references to plan identifiers, NARROWED TO ONE SITE. Sites (1) and (3) of the original row are CLOSED by commit 00de767e9a and must not be re-hunted: the modelo edit-dependency and operations financial-operand receipt validators no longer cite a vault stem, path, ADR identifier or predecessor artifact -- their docstrings now read as plain production-invariant descriptions and a tree-wide grep for a vault path across src/ returns zero -- and the TUI operation modal test no longer builds a path to a vault document or asserts on its text. What REMAINS is site (2): bare plan container identifiers embedded in shipped production docstrings and comments, of which the Workspace projection module is the last holder at 31 occurrences including the only full W##.P##.S## address anywhere in production source. Its sibling modules and the scattered non-workspace holders were swept in commit 54778350d0. Replace the identifier with the domain reason it stands for; do not delete the sentence and do not rename the constant. The gate that owns this rule is scope-flagged per pattern and currently test-scoped for step notation, so it reports green over these; the flip is tracked as its own row in the interface plan

## Scope

- `src/cadrumo/application/modelo/workspace.py`
- `blocked on the peer lane currently holding uncommitted changes in that file`

## Changes

- `M` `src/cadrumo/application/cli_exception_preconditions.py`
- `M` `src/cadrumo/application/aggregation/_foreign_assets.py`
- `M` `src/cadrumo/application/ledger/llm_classification.py`
- `M` `src/cadrumo/application/operator_surface/action_resolution.py`
- `M` `src/cadrumo/application/storage/calc_sheets/_row_set_assembly.py`
- `M` `src/cadrumo/adapters/persistence/profile/transactions.py`
- `M` `src/cadrumo/adapters/persistence/storage/custody/recovery.py`
- `M` `src/cadrumo/domain/calculations/registry/applicability.py`
- `M` `src/cadrumo/domain/iva/_regimen_simplificado_rows.py`
- `M` `src/cadrumo/entrypoints/cli/errors.py`
- `M` `src/cadrumo/entrypoints/cli/_operator_surface_reconciliation.py`
- `M` `src/cadrumo/entrypoints/cli/_config/_check_payloads.py`
- `verify:` `git diff --numstat` -> `17 changed, 17 added, 12 files`
- `verify:` `ruff check` -> `pass (8 pre-existing errors confirmed at HEAD via --stdin-filename)`

## Notes

PARTIAL: the safe half only. 17 Step-id citations removed from production
docstrings and comments, each replaced with the domain reason it stood for
(S87 -> the observation assembler; S05 -> the verb input schema; S03 -> the
supervised KDF boundary).

Deliberately NOT taken, and still open on this row:

- Step ids carried as shipped VALUES rather than comments -- `"W09-P17-S257"`,
  `label="S39 ..."`, `surface="S56 ..."`, `"S165-PRIVATE-..."` x5,
  `label="S92 ..."` x6, and `provenance="S05 VerbInputSchema.required_inputs"`
  at `_operator_surface_reconciliation.py:144`. These flow through assertions
  and persisted records; editing them changes test data, not commentary.
- Three matches that are legitimate domain data, not Step ids: an invoice
  number and two justificante CSV evidence references (`CSV-303-2026-2T-S21`,
  `CSV-303-2025-1T-S21`). A blanket sweep would corrupt filing evidence.
- `application/modelo/_edit_models.py` (2 sites), adjacent to another lane.
- 18 production sites in files another lane held at the time of the sweep.

THIS INVENTORY HAS GROWN AT EVERY MEASUREMENT: the row said 2 sites, a
later sweep found ~31, this measurement found ~55, and the production total
was 36 of which 18 were peer-held at that instant. Treat any figure here as
a FLOOR and re-measure before scoping.
