---
tags:
  - '#exec'
  - '#filing-chain-reconciliation'
date: '2026-09-17'
modified: '2026-09-17'
body_schema: 'body-v2'
body_hash: 'sha256:589d7deb12c35dba9a07fcf3a808523bc808a9f1798920bb38ac13ebd706abb5'
related:
  - "[[2026-09-17-filing-chain-reconciliation-plan]]"
---

<!-- Machine-owned, whole file: `vaultspec-core vault exec log` creates it
     on first use and appends every row; never hand-edit it. Add no
     frontmatter fields. Wiki-links belong in `related:` only.

     ONE ledger per plan, the only execution artifact. Each row's first
     column names its Step. -->

# `filing-chain-reconciliation` ledger

## Changes

<!-- MECHANICAL LOG, append-only, one row per path touched per Step, written
     by `--row`:
       - `S##` `A` `path`   added
       - `S##` `M` `path`   modified
       - `S##` `D` `path`   deleted
       - `S##` `R` `old` -> `new`   renamed
     Paths are repo-relative, in backticks. No prose: the Step row states the
     intent and the commit carries the diff.

     Optional per-Step rows, written by `--verify` and `--by`:
       - `S##` `verify:` `<command>` -> `pass` | `fail`
       - `S##` `by:` `<persona>`

     Rows are appended in Step order and never rewritten. Only rows in this
     section register a Step as covered. `--note` adds a `## Notes` section
     ONLY on exception (data loss, skipped work, a scaffold left in code, a
     persistent failure), one `S##`-prefixed line each; it is otherwise
     omitted. -->
- `S01` `M` `src/cadrumo/domain/modelos/filing_record.py`
- `S01` `A` `src/cadrumo/domain/modelos/tests/test_filing_chain_record.py`
- `S01` `verify:` `ruff+ty on feature files` -> `pass`
- `S01` `by:` `backend-opus`
- `S02` `A` `src/cadrumo/application/modelo/filing_chain_reconciliation.py`
- `S02` `A` `src/cadrumo/application/modelo/tests/test_filing_chain_reconciliation.py`
- `S02` `M` `src/cadrumo/application/modelo/external_import_actions.py`
- `S02` `M` `src/cadrumo/application/modelo/reconciliation.py`
- `S02` `verify:` `pytest feature set (67+488 tests; failures outside the feature or under repair)` -> `pass`
- `S02` `by:` `backend-opus`
- `S03` `M` `src/cadrumo/adapters/persistence/profile/calculation_observations.py`
- `S03` `M` `src/cadrumo/application/calculations/observations_repository.py`
- `S03` `M` `src/cadrumo/application/modelo/local_observation_actions.py`
- `S03` `D` `src/cadrumo/adapters/persistence/profile/tests/test_observation_evidence_displacement_guard.py`
- `S03` `A` `src/cadrumo/adapters/persistence/profile/tests/test_observation_layers_and_overrides.py`
- `S03` `verify:` `pytest feature set (67+488 tests; failures outside the feature or under repair)` -> `pass`
- `S03` `by:` `backend-opus`
- `S04` `M` `src/cadrumo/application/modelo/amendment_actions.py`
- `S04` `M` `src/cadrumo/application/modelo/revision_persistence.py`
- `S04` `M` `src/cadrumo/application/live/filed_observation_persistence.py`
- `S04` `M` `src/cadrumo/application/calculations/cross_period_external_evidence.py`
- `S04` `A` `src/cadrumo/adapters/persistence/profile/tests/test_amend_pending_chain.py`
- `S04` `verify:` `pytest feature set (67+488 tests; failures outside the feature or under repair)` -> `pass`
- `S04` `by:` `backend-opus`
- `S06` `M` `src/cadrumo/entrypoints/tui/declarations/filing_history.py`
- `S06` `M` `src/cadrumo/entrypoints/tui/declarations/controller.py`
- `S06` `M` `src/cadrumo/application/modelo/declarations_workspace.py`
- `S06` `M` `src/cadrumo/application/workbench_generation.py`
- `S06` `A` `src/cadrumo/entrypoints/tui/declarations/tests/test_filing_chain_history.py`
- `S06` `verify:` `pytest test_filing_chain_history.py test_declarations_workspace.py` -> `pass`
- `S06` `by:` `surfaces-opus`
- `S07` `A` `src/cadrumo/entrypoints/cli/tests/test_filing_chain_reconciliation_cli.py`
- `S07` `A` `src/cadrumo/entrypoints/cli/tests/_recorded_sede_filed_port.py`
- `S07` `verify:` `pytest test_filing_chain_reconciliation_cli.py` -> `pass`
- `S07` `by:` `surfaces-opus`
- `S05` `M` `src/cadrumo/entrypoints/cli/_modelo_records_cli.py`
- `S05` `A` `src/cadrumo/entrypoints/cli/_filing_chain_payloads.py`
- `S05` `M` `src/cadrumo/entrypoints/cli/_app_live.py`
- `S05` `M` `src/cadrumo/entrypoints/live_state_composition.py`
- `S05` `M` `src/cadrumo/application/modelo/local_observation_spreadsheet.py`
- `S05` `verify:` `pytest test_modelo_local_observation_cli.py test_modelo_local_observation_spreadsheet_cli.py test_modelo_filing_record.py` -> `pass`
- `S05` `by:` `surfaces-opus`

## Notes

- `S01` No stored-row upgrader: filing catalogue and observation namespaces bumped to schema version 2, so older rows refuse explicitly (no released compatibility floor).
- `S04` tipo_solicitud to declaration-kind mapping reads the words complementaria/sustitutiva/rectificativa; the vocabulary is unverified against an AEAT list and unknown values stay undeclared.

