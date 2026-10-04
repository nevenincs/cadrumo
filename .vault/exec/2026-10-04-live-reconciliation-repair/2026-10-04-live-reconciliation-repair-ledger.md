---
tags:
  - '#exec'
  - '#live-reconciliation-repair'
date: '2026-10-04'
modified: '2026-10-04'
body_schema: 'body-v2'
body_hash: 'sha256:c7460644ac0ea093e045895a9802f428d4cf692616a0070a79fef528553fc504'
related:
  - "[[2026-10-04-live-reconciliation-repair-plan]]"
---

<!-- Machine-owned, whole file: `vaultspec-core vault exec log` creates it
     on first use and appends every row; never hand-edit it. Add no
     frontmatter fields. Wiki-links belong in `related:` only.

     ONE ledger per plan, the only execution artifact. Each row's first
     column names its Step. -->

# `live-reconciliation-repair` ledger

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

- `S01` `M` `src/cadrumo/application/operations/_public_mirror_projection.py`
- `S01` `M` `src/cadrumo/application/tests/test_workbench_generation_operation.py`
- `S01` `verify:` `focused generation unit and integration suite 48 tests` -> `pass`
- `S01` `verify:` `scoped Ruff format and lint` -> `pass`
- `S01` `verify:` `scoped ty basedpyright pyrefly` -> `pass`
- `S01` `by:` `vaultspec-standard-executor`
- `S02` `M` `src/cadrumo/application/live/justificante.py`
- `S02` `M` `src/cadrumo/application/live/justificante_ports.py`
- `S02` `M` `src/cadrumo/application/live/tests/test_justificante_capture_resolution.py`
- `S02` `M` `src/cadrumo/entrypoints/justificante_composition.py`
- `S02` `M` `src/cadrumo/entrypoints/tests/test_justificante_capture_operation.py`
- `S02` `M` `src/cadrumo/adapters/outbound/aeat/sede/declarations.py`
- `S02` `A` `src/cadrumo/adapters/outbound/aeat/sede/tests/test_register_justificante_capture.py`
- `S02` `M` `.vault/adr/2026-06-10-live-justificante-reconcile-adr.md`
- `S02` `verify:` `focused receipt resolution capture unit integration 13 tests` -> `pass`
- `S02` `verify:` `scoped Ruff style format and ty` -> `pass`
- `S02` `by:` `vaultspec-high-executor`
- `S03` `M` `src/cadrumo/domain/calculations/registry/export_parse.py`
- `S03` `M` `src/cadrumo/adapters/outbound/aeat/sede/declarations_observations.py`
- `S03` `A` `src/cadrumo/domain/calculations/registry/tests/test_filed_payload.py`
- `S03` `A` `src/cadrumo/adapters/outbound/aeat/sede/tests/test_filed_payload_context.py`
- `S03` `verify:` `filed payload envelope value policy identity and source availability 306 tests` -> `pass`
- `S03` `verify:` `scoped Ruff format lint ty basedpyright pyrefly` -> `pass`
- `S03` `verify:` `retained encrypted AEAT2024Q1 payload 129fields71casillas` -> `pass`
- `S03` `by:` `vaultspec-standard-executor`
- `S06` `M` `src/cadrumo/application/modelo/reconciliation.py`
- `S06` `M` `src/cadrumo/application/modelo/reconciliation_pull_operation.py`
- `S06` `M` `src/cadrumo/application/modelo/reconciliation_records.py`
- `S06` `M` `src/cadrumo/application/modelo/reconciliation_list_operation.py`
- `S06` `M` `src/cadrumo/entrypoints/operation_composition.py`
- `S06` `M` `src/cadrumo/entrypoints/justificante_composition.py`
- `S06` `M` `src/cadrumo/entrypoints/cli/_modelo_nonwork_reconcile_command_specs.py`
- `S06` `M` `src/cadrumo/entrypoints/cli/_modelo_reconcile_cli.py`
- `S06` `M` `src/cadrumo/entrypoints/cli/_modelo_payloads_m036.py`
- `S06` `M` `src/cadrumo/entrypoints/cli/runtime_modelo_reconciliation_pull.py`
- `S06` `M` `src/cadrumo/entrypoints/cli/runtime_filed_single.py`
- `S06` `M` `src/cadrumo/entrypoints/cli/tests/test_runtime_modelo_reconciliation_pull.py`
- `S06` `M` `src/cadrumo/entrypoints/tests/test_modelo_reconciliation_pull_operation.py`
- `S06` `M` `src/cadrumo/locales/ca/cli.yml`
- `S06` `M` `src/cadrumo/locales/en/cli.yml`
- `S06` `M` `src/cadrumo/locales/es/cli.yml`
- `S06` `M` `src/cadrumo/locales/hu/cli.yml`
- `S06` `verify:` `scoped operation and CLI regressions 22 tests` -> `pass`
- `S06` `verify:` `source selection tests 6 tests` -> `pass`
- `S06` `verify:` `scoped Ruff and ty` -> `pass`
- `S06` `by:` `vaultspec-high-executor`
- `S04` `M` `src/cadrumo/application/aeat_sync/_workspace_projection.py`
- `S04` `M` `src/cadrumo/application/aeat_sync/workspace.py`
- `S04` `M` `src/cadrumo/application/aeat_sync/workspace_reader.py`
- `S04` `A` `src/cadrumo/application/aeat_sync/reconciliation_reader.py`
- `S04` `A` `src/cadrumo/application/aeat_sync/tests/test_reconciliation_reader.py`
- `S04` `M` `src/cadrumo/application/aeat_sync/tests/test_workspace.py`
- `S04` `M` `src/cadrumo/application/workbench_generation_reader.py`
- `S04` `M` `src/cadrumo/application/workbench_generation_public_contracts.py`
- `S04` `M` `src/cadrumo/entrypoints/workbench_generation_composition.py`
- `S04` `M` `src/cadrumo/entrypoints/tui/aeat_sync/controller.py`
- `S04` `M` `src/cadrumo/entrypoints/tui/aeat_sync/screens.py`
- `S04` `M` `src/cadrumo/entrypoints/tui/aeat_sync/tests/test_aeat_sync_workspace.py`
- `S04` `M` `src/cadrumo/locales/ca/common.yml`
- `S04` `M` `src/cadrumo/locales/en/common.yml`
- `S04` `M` `src/cadrumo/locales/es/common.yml`
- `S04` `M` `src/cadrumo/locales/hu/common.yml`
- `S04` `verify:` `application AEAT Sync TUI and generation 167 tests` -> `pass`
- `S04` `verify:` `final preservation and TUI focused 12 tests` -> `pass`
- `S04` `verify:` `overview unavailable route 3 tests` -> `pass`
- `S04` `verify:` `scoped Ruff format and ty basedpyright pyrefly` -> `pass`
- `S04` `verify:` `review known drift preservation incomplete summary historical identity` -> `pass`
- `S04` `by:` `vaultspec-high-executor`
- `S07` `M` `src/cadrumo/_data/registry/aeat/facts/2025/mapping/0086-2025-modelo-303-carry-disposition-verification-mapping.toml`
- `S07` `M` `src/cadrumo/application/calculations/m303_carry_ingress.py`
- `S07` `M` `src/cadrumo/application/calculations/tests/test_m303_carry_mapping_revision_selection.py`
- `S07` `M` `src/cadrumo/adapters/persistence/profile/tests/cross_period_clean_state_support.py`
- `S07` `M` `src/cadrumo/adapters/persistence/profile/tests/filed_capture_history_support.py`
- `S07` `M` `src/cadrumo/adapters/persistence/profile/tests/modelo_303_filed_disposition.py`
- `S07` `M` `src/cadrumo/adapters/persistence/profile/tests/test_carry_gate_parity.py`
- `S07` `M` `src/cadrumo/adapters/persistence/profile/tests/test_iva_compensation_filed_observations.py`
- `S07` `M` `src/cadrumo/adapters/persistence/profile/tests/test_iva_compensation_relation_prefill.py`
- `S07` `M` `src/cadrumo/adapters/persistence/profile/tests/test_m303_carry_ingress.py`
- `S07` `M` `src/cadrumo/adapters/persistence/profile/tests/test_observation_header_facts_roundtrip.py`
- `S07` `M` `src/cadrumo/adapters/persistence/profile/tests/test_observation_scan_key_identity.py`
- `S07` `M` `src/cadrumo/adapters/persistence/profile/tests/test_observations_repository_roundtrip.py`
- `S07` `M` `src/cadrumo/adapters/persistence/profile/tests/test_prorrata_regularizacion_advisory.py`
- `S07` `M` `src/cadrumo/adapters/persistence/profile/tests/test_revision_stamp_roundtrip.py`
- `S07` `M` `src/cadrumo/adapters/persistence/profile/tests/test_terminal_preconditions.py`
- `S07` `M` `src/cadrumo/entrypoints/cli/tests/test_overview_calendar_local_evidence.py`
- `S07` `M` `src/cadrumo/entrypoints/tests/profile_persistence/_iva_wallet_engine_support.py`
- `S07` `M` `src/cadrumo/entrypoints/tests/profile_persistence/test_export_output_paths.py`
- `S07` `M` `src/cadrumo/entrypoints/tests/profile_persistence/test_filed_header_facts_reach_storage.py`
- `S07` `M` `src/cadrumo/entrypoints/tests/profile_persistence/test_iva_compensation_provenance_population.py`
- `S07` `M` `src/cadrumo/entrypoints/tests/profile_persistence/test_iva_wallet_engine_integration.py`
- `S07` `M` `.vault/adr/2026-06-21-m303-carry-reconciliation-adr.md`
- `S07` `verify:` `canonical historical header parity ingress storage and carry 34 tests` -> `pass`
- `S07` `verify:` `scoped Ruff format and ty` -> `pass`
- `S07` `verify:` `isolated authority publication fixed input snapshot` -> `pass`
- `S07` `verify:` `retained real filing 71 numeric fields observation envelope preparation` -> `pass`
- `S07` `by:` `vaultspec-high-executor`

## Notes

- `S02` Live authentication request expired; fresh pull acceptance belongs to S05. Broader adapter tests exposed unavailable browser provisioning and preexisting export fixture disagreement.
- `S03` Shared export parser includes unrelated preexisting XML and signed-component edits; checkpoint stages only filed-input hunks. Broader legacy fixture and browser provisioning failures remain outside this Step.
- `S06` Live declaration capture reached registry enrollment but failed finalization; lead continues diagnosing upstream enrollment during S05.
