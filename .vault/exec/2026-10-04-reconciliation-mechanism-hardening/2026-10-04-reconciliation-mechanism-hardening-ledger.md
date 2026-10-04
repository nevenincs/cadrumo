---
tags:
  - '#exec'
  - '#reconciliation-mechanism-hardening'
date: '2026-10-04'
modified: '2026-10-04'
body_schema: 'body-v2'
body_hash: 'sha256:e643998e8a3c6424fde530f9aa63cdccce6dc48d6b5e505cea42a37b3d5d4aeb'
related:
  - "[[2026-10-04-reconciliation-mechanism-hardening-plan]]"
---

# `reconciliation-mechanism-hardening` ledger

## Changes

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
- `S06` `M` `src/cadrumo/application/aeat_sync/_workspace_projection.py`
- `S06` `M` `src/cadrumo/application/aeat_sync/reconciliation_reader.py`
- `S06` `M` `src/cadrumo/application/aeat_sync/tests/test_reconciliation_reader.py`
- `S06` `M` `src/cadrumo/application/aeat_sync/workspace.py`
- `S06` `M` `src/cadrumo/application/search/installed_workbench.py`
- `S06` `M` `src/cadrumo/application/search/tests/test_installed_workbench.py`
- `S06` `M` `src/cadrumo/application/workbench_generation_public_contracts.py`
- `S06` `M` `src/cadrumo/entrypoints/tui/aeat_sync/screens.py`
- `S06` `M` `src/cadrumo/entrypoints/tui/aeat_sync/tests/test_aeat_sync_workspace.py`
- `S06` `M` `src/cadrumo/locales/en/common.yml`
- `S06` `M` `src/cadrumo/locales/es/common.yml`
- `S06` `M` `src/cadrumo/locales/ca/common.yml`
- `S06` `M` `src/cadrumo/locales/hu/common.yml`
- `S06` `verify:` `78 AEAT Sync and search unit tests` -> `pass`
- `S06` `verify:` `106 AEAT Sync integration tests` -> `pass`
- `S06` `verify:` `11 persisted comparison readback tests and exact revision TUI detail test` -> `pass`
- `S06` `verify:` `scoped Ruff format ty basedpyright pyrefly and 11-file canonical private imports` -> `pass`
- `S06` `verify:` `manual runtime actual CLI exact-ID receipt import and history` -> `pass`
- `S06` `verify:` `manual runtime installed uninstrumented TUI 4 comparisons 30 rows 28 differences` -> `pass`
- `S06` `verify:` `encrypted history local calculation unchanged and no local filing created` -> `pass`
- `S06` `verify:` `independent integrated code and manual-runtime review` -> `pass`
- `S06` `by:` `root`

## Notes

- `S06` Two earlier TUI startup attempts timed out; later installed runs and final manual-owner acceptance passed. Startup reliability is not claimed fixed.
- `S06` Repository-wide import gate not green; unrelated generated metadata and concurrent changes excluded.
