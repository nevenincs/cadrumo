---
tags:
  - '#exec'
  - '#reconciliation-mechanism-hardening'
date: '2026-10-04'
modified: '2026-10-04'
body_schema: 'body-v2'
body_hash: 'sha256:57e912b816e54158115add4ea0500a08fcb0f0ad48ebd148602c37e2641d058f'
related:
  - "[[2026-10-04-reconciliation-mechanism-hardening-plan]]"
---

<!-- Machine-owned, whole file: `vaultspec-core vault exec log` creates it
     on first use and appends every row; never hand-edit it. Add no
     frontmatter fields. Wiki-links belong in `related:` only.

     ONE ledger per plan, the only execution artifact. Each row's first
     column names its Step. -->

# `reconciliation-mechanism-hardening` ledger

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

- `S01` `M` `src/cadrumo/application/modelo/pulled_filing_reconcile.py`
- `S01` `M` `src/cadrumo/application/modelo/verification_model_findings.py`
- `S01` `M` `src/cadrumo/adapters/persistence/profile/tests/test_pulled_filing_divergence_reconcile.py`
- `S01` `verify:` `focused encrypted working-calculation tests (11 cases)` -> `pass`
- `S01` `verify:` `scoped Ruff format ty basedpyright pyrefly private-import checks` -> `pass`
- `S01` `verify:` `independent S01 code review` -> `pass`
- `S01` `by:` `mirror_fix`
- `S02` `M` `src/cadrumo/application/modelo/filing_chain_reconciliation.py`
- `S02` `M` `src/cadrumo/entrypoints/tests/test_filing_chain_reconciliation.py`
- `S02` `M` `src/cadrumo/locales/en/application.yml`
- `S02` `M` `src/cadrumo/locales/es/application.yml`
- `S02` `M` `src/cadrumo/locales/ca/application.yml`
- `S02` `M` `src/cadrumo/locales/hu/application.yml`
- `S02` `verify:` `pytest -n0 test_filing_chain_reconciliation.py (23 cases)` -> `pass`
- `S02` `verify:` `scoped Ruff format ty basedpyright pyrefly and canonical private-import checks` -> `pass`
- `S02` `verify:` `independent S02 corrected replay review` -> `pass`
- `S02` `by:` `root`
- `S03` `M` `src/cadrumo/application/modelo/_m303_m349_reconcile.py`
- `S03` `M` `src/cadrumo/application/modelo/tests/test_m303_m349_intracom_reconcile.py`
- `S03` `A` `src/cadrumo/adapters/persistence/profile/tests/test_cross_model_reconciliation_persistence.py`
- `S03` `M` `src/cadrumo/application/modelo/finding_message_text.py`
- `S03` `A` `src/cadrumo/entrypoints/tests/reconciliation_finding_fixtures.py`
- `S03` `M` `src/cadrumo/entrypoints/cli/tests/test_modelo_verification_report_view.py`
- `S03` `M` `src/cadrumo/entrypoints/tui/modelo/workbench/tests/test_workbench_finding_words.py`
- `S03` `M` `src/cadrumo/locales/en/application.yml`
- `S03` `M` `src/cadrumo/locales/es/application.yml`
- `S03` `M` `src/cadrumo/locales/ca/application.yml`
- `S03` `M` `src/cadrumo/locales/hu/application.yml`
- `S03` `verify:` `combined working and cross-model tests (32 cases)` -> `pass`
- `S03` `verify:` `CLI TUI and shared finding renderer tests (13 cases)` -> `pass`
- `S03` `verify:` `scoped Ruff format ty basedpyright pyrefly canonical private-import checks` -> `pass`
- `S03` `verify:` `independent S03 review including renderer correction` -> `pass`
- `S03` `by:` `mirror_fix`
- `S05` `M` `src/cadrumo/application/modelo/reconciliation.py`
- `S05` `M` `src/cadrumo/application/modelo/reconciliation_records.py`
- `S05` `M` `src/cadrumo/application/modelo/reconciliation_pull_operation.py`
- `S05` `M` `src/cadrumo/application/modelo/reconciliation_import_operation.py`
- `S05` `M` `src/cadrumo/application/modelo/reconciliation_list_operation.py`
- `S05` `M` `src/cadrumo/entrypoints/cli/_modelo_reconcile_cli.py`
- `S05` `M` `src/cadrumo/entrypoints/cli/_payloads_modelo_reconcile.py`
- `S05` `M` `src/cadrumo/entrypoints/cli/_modelo_payloads_m036.py`
- `S05` `M` `src/cadrumo/entrypoints/cli/_modelo_nonwork_reconcile_command_specs.py`
- `S05` `M` `src/cadrumo/entrypoints/cli/runtime_modelo_reconciliation_pull.py`
- `S05` `M` `src/cadrumo/entrypoints/cli/runtime_modelo_reconciliation_import.py`
- `S05` `A` `src/cadrumo/adapters/persistence/profile/tests/test_reconciliation_revision_provenance.py`
- `S05` `M` `src/cadrumo/entrypoints/tests/test_modelo_reconciliation_pull_operation.py`
- `S05` `M` `src/cadrumo/locales/en/cli.yml`
- `S05` `M` `src/cadrumo/locales/es/cli.yml`
- `S05` `M` `src/cadrumo/locales/ca/cli.yml`
- `S05` `M` `src/cadrumo/locales/hu/cli.yml`
- `S05` `verify:` `37 focused reconciliation and 3 provenance coverage tests` -> `pass`
- `S05` `verify:` `7 registered pull-operation tests including explicit missing-ID refusal` -> `pass`
- `S05` `verify:` `Ruff format ty basedpyright pyrefly canonical private static imports` -> `pass`
- `S05` `verify:` `actual CLI explicit-revision retained receipt import and encrypted readback` -> `pass`
- `S05` `verify:` `independent S05 review` -> `pass`
- `S05` `by:` `receipt_fix`
- `S04` `M` `src/cadrumo/application/modelo/iva_wallet_gate.py`
- `S04` `M` `src/cadrumo/application/modelo/iva_wallet_seed.py`
- `S04` `M` `src/cadrumo/domain/iva_compensation/reconciliation.py`
- `S04` `M` `src/cadrumo/application/modelo/export.py`
- `S04` `M` `src/cadrumo/application/modelo/filing_actions.py`
- `S04` `M` `src/cadrumo/application/modelo/verification_gate_findings.py`
- `S04` `M` `src/cadrumo/application/modelo/verification_actions.py`
- `S04` `M` `src/cadrumo/application/modelo/export_ports.py`
- `S04` `M` `src/cadrumo/entrypoints/adapter_composition.py`
- `S04` `M` `src/cadrumo/entrypoints/live_state_composition.py`
- `S04` `M` `src/cadrumo/adapters/persistence/profile/calculation_observations.py`
- `S04` `M` `src/cadrumo/adapters/persistence/profile/tests/test_iva_wallet_correction.py`
- `S04` `M` `src/cadrumo/adapters/persistence/profile/tests/modelo_export_ports_support.py`
- `S04` `M` `src/cadrumo/entrypoints/tests/profile_persistence/_iva_wallet_engine_support.py`
- `S04` `M` `src/cadrumo/entrypoints/tests/profile_persistence/test_iva_wallet_engine_lifecycle_gate.py`
- `S04` `M` `src/cadrumo/entrypoints/tests/profile_persistence/test_iva_wallet_engine_overrides.py`
- `S04` `M` `src/cadrumo/entrypoints/tests/profile_persistence/test_iva_wallet_engine_filing.py`
- `S04` `M` `src/cadrumo/entrypoints/tests/profile_persistence/test_export_iva_wallet.py`
- `S04` `verify:` `33 wallet lifecycle domain live and encrypted persistence tests` -> `pass`
- `S04` `verify:` `23 correction override and history tests` -> `pass`
- `S04` `verify:` `9 verify file refile export tests` -> `pass`
- `S04` `verify:` `Ruff format ty basedpyright pyrefly canonical private static imports` -> `pass`
- `S04` `verify:` `independent S04 review` -> `pass`
- `S04` `by:` `receipt_fix`
