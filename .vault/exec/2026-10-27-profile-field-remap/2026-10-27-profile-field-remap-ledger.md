---
tags:
  - '#exec'
  - '#profile-field-remap'
date: '2026-10-27'
modified: '2026-10-27'
body_schema: 'body-v2'
body_hash: 'sha256:49aaeb4dc1eb4df8f1f14b082d0029cb901e4fd2e8f95f20ddc21ee2ec2cf10d'
related:
  - "[[2026-10-27-profile-field-remap-plan]]"
---

<!-- Machine-owned, whole file: `vaultspec-core vault exec log` creates it
     on first use and appends every row; never hand-edit it. Add no
     frontmatter fields. Wiki-links belong in `related:` only.

     ONE ledger per plan, the only execution artifact. Each row's first
     column names its Step. -->

# `profile-field-remap` ledger

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

- `S06` `M` `.vault/adr/2026-10-04-desktop-shell-adr.md`
- `S06` `verify:` `vaultspec-core vault check all -f desktop-shell` -> `pass`
- `S05` `A` `src/cadrumo/application/aggregation/tests/usage_ratio_support.py`
- `S05` `M` `src/cadrumo/application/aggregation/_renta_business_eligibility.py`
- `S05` `M` `src/cadrumo/application/aggregation/_shared_issue_reasons.py`
- `S05` `M` `src/cadrumo/application/aggregation/renta_ledger.py`
- `S05` `M` `src/cadrumo/application/aggregation/renta_gasto_ledger.py`
- `S05` `M` `src/cadrumo/application/aggregation/modelo_bindings.py`
- `S05` `M` `src/cadrumo/application/aggregation/ledger_membership.py`
- `S05` `M` `src/cadrumo/application/modelo/calculation_actions.py`
- `S05` `M` `src/cadrumo/domain/renta/ledger_expenses.py`
- `S05` `M` `src/cadrumo/application/aggregation/tests/test_renta_ledger.py`
- `S05` `M` `src/cadrumo/application/aggregation/tests/test_renta_gasto_aggregation.py`
- `S05` `M` `src/cadrumo/application/aggregation/tests/test_modelo_source_mesh_ledger.py`
- `S05` `M` `src/cadrumo/application/aggregation/tests/test_currency_conversion_pipeline_parity.py`
- `S05` `M` `src/cadrumo/application/aggregation/tests/test_shared_issue_reasons.py`
- `S05` `verify:` `pytest aggregation renta ledger M130 resolver parity reasons preflight-home-office tests (128)` -> `pass`
- `S05` `verify:` `pytest aggregation modelo ledger persistence-profile domain-renta usage_ratios profile_persistence (8921)` -> `fail`
- `S05` `verify:` `ruff check src/cadrumo/application src/cadrumo/domain/renta` -> `pass`
- `S05` `verify:` `ruff format --check src/cadrumo/application src/cadrumo/domain/renta` -> `pass`
- `S05` `verify:` `lint-imports --config .importlinter` -> `pass`
- `S05` `by:` `vaultspec-standard-executor`

## Notes

- `S05` Covering run: 7 failures not caused by S05 -- 6 caplog log-capture assertions in modules that do not load the changed code `(test_source_mesh,` `test_binding_readiness` x2, `test_state_projection,` `test_transactions_repository,` `test_modelo_source_mesh_ledger_integration)` and `test_atribucion_member_required_set,` which tracks the S01 schema edit. check-types: 4 ty diagnostics, all in `src/cadrumo_runtime/adapters/tests/test_profile_worker_startup.py` (concurrent runtime work). `import_gate:` 30 contracts kept, 0 hard findings, 0 load failures; verdict unavailable because the shared tree changed during the run.
