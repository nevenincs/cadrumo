---
tags:
  - '#exec'
  - '#censal-surface-parser'
date: '2026-10-03'
modified: '2026-10-03'
body_schema: 'body-v2'
body_hash: 'sha256:18075fd27ad870fe901ff0f40272f7927cd07c0e94a36fd533b7e223ccc66b3a'
related:
  - "[[2026-10-03-censal-surface-parser-plan]]"
---

# `censal-surface-parser` ledger

## Changes

- `S01` `M` `src/cadrumo/adapters/outbound/aeat/sede/censal_datos.py`
- `S01` `A` `src/cadrumo/adapters/outbound/aeat/sede/censal_navigation.py`
- `S01` `A` `src/cadrumo/adapters/outbound/aeat/sede/censal_tables.py`
- `S01` `A` `src/cadrumo/adapters/outbound/aeat/sede/censal_tax_status.py`
- `S01` `M` `src/cadrumo/application/user_profile/censal_observation.py`
- `S01` `M` `src/cadrumo/application/user_profile/censal_operation.py`
- `S01` `M` `src/cadrumo/core/external_constants.py`
- `S01` `M` `src/cadrumo/adapters/outbound/aeat/sede/tests/test_censal_datos.py`
- `S01` `A` `src/cadrumo/adapters/outbound/aeat/sede/tests/test_censal_consultations.py`
- `S01` `A` `src/cadrumo/adapters/outbound/aeat/sede/tests/censal_consultation_fixtures.py`
- `S01` `M` `src/cadrumo/entrypoints/tests/test_censal_operation_operand.py`
- `S01` `M` `src/cadrumo/entrypoints/tests/censal_review_test_support.py`
- `S01` `M` `src/cadrumo/entrypoints/cli/config/_censo_transport.py`
- `S01` `M` `dev/quality/metadata/import_load_targets.json`
- `S01` `verify:` `focused census pytest (105 passing plus 3 corrected sync tests)` -> `pass`
- `S01` `verify:` `Ruff check and format scoped census files` -> `pass`
- `S01` `verify:` `ty check census driver observation operand and helper` -> `pass`
- `S01` `verify:` `production Clave Movil own-name pull and encrypted observation parity` -> `pass`
- `S01` `verify:` `python -m dev.quality.import_load_probe --report .tmp/censal-import-loadability.json` -> `pass`
- `S01` `verify:` `python -m dev.quality.types` -> `fail`
- `S01` `verify:` `python -m dev.quality.import_gate` -> `fail`
- `S01` `M` `src/cadrumo/core/external_constants.toml`
- `S02` `A` `src/cadrumo/application/user_profile/censal_readback.py`
- `S02` `A` `src/cadrumo/entrypoints/censal_readback_composition.py`
- `S02` `M` `src/cadrumo/application/user_profile/censal_preview_operation.py`
- `S02` `M` `src/cadrumo/application/user_profile/censal_prepare_operation.py`
- `S02` `M` `src/cadrumo/application/aeat_sync/workspace.py`
- `S02` `M` `src/cadrumo/application/aeat_sync/_workspace_projection.py`
- `S02` `M` `src/cadrumo/application/aeat_sync/workspace_reader.py`
- `S02` `M` `src/cadrumo/application/aeat_sync/tests/test_workspace_reader.py`
- `S02` `M` `src/cadrumo/application/workbench_generation_reader.py`
- `S02` `M` `src/cadrumo/application/tests/test_workbench_generation.py`
- `S02` `M` `src/cadrumo/entrypoints/operation_composition.py`
- `S02` `M` `src/cadrumo/entrypoints/workbench_generation_composition.py`
- `S02` `M` `src/cadrumo/entrypoints/cli/_profile_authentication_gate.py`
- `S02` `M` `src/cadrumo/entrypoints/cli/config/_censo_payloads.py`
- `S02` `M` `src/cadrumo/entrypoints/cli/config/_censo_transport.py`
- `S02` `M` `src/cadrumo/entrypoints/cli/config/profile_command_specs.py`
- `S02` `M` `src/cadrumo/entrypoints/cli/config/tests/test_censo_pull_verb.py`
- `S02` `M` `src/cadrumo/entrypoints/tui/aeat_sync/screens.py`
- `S02` `M` `src/cadrumo/entrypoints/tui/aeat_sync/tests/test_aeat_sync_workspace.py`
- `S02` `M` `src/cadrumo/entrypoints/tests/test_censal_preview_operation.py`
- `S02` `M` `src/cadrumo/entrypoints/tests/test_censal_sync_operations.py`
- `S02` `M` `src/cadrumo/locales/en/cli.yml`
- `S02` `M` `src/cadrumo/locales/es/cli.yml`
- `S02` `M` `src/cadrumo/locales/ca/cli.yml`
- `S02` `M` `src/cadrumo/locales/hu/cli.yml`
- `S02` `M` `dev/quality/metadata/import_load_targets.json`
- `S02` `verify:` `focused CLI/TUI/workspace/preview/review suite (132 passed; two reviewed-readback failures)` -> `fail`
- `S02` `verify:` `pytest test_censal_sync_operations.py -k complete_capture -m integration (two corrected tests)` -> `pass`
- `S02` `verify:` `pytest test_workbench_generation.py test_censo_pull_verb.py -m unit-or-integration (48 tests)` -> `pass`
- `S02` `verify:` `scoped Ruff and ty S02 production and persistence test modules` -> `pass`
- `S02` `verify:` `python -m dev.quality.import_load_probe --compile-targets (retry after transient file contention)` -> `pass`
- `S02` `verify:` `python -m dev.quality.import_load_probe --report .tmp/censal-s02-imports.json (4337 loaded; zero failures)` -> `pass`
- `S02` `verify:` `installed CLI/TUI native profile admission in agent Windows Session 0` -> `fail`
- `S02` `by:` `codex`

## Notes

- `S01` Implementation verified live. Step remains open for repository-wide type and boundary gate failures documented in the audit. Concurrent snapshot f4729489f9 includes the early changes; subsequent corrections remain in the shared working tree.
- `S01` Path correction: the earlier `_data/external_constants.toml` ledger row was a transcription error. The changed source is `core/external_constants.toml;` no `_data` file was changed.
- `S02` S02 remains open. Native transport connects, but both frontends refuse Session 0 at the real Windows desktop witness before AEAT access. No guard bypassed. Desktop verifier prepared at .tmp/censal-ui-verify.py; normal interactive desktop execution and Clave approval are still required.
- `S02` One encrypted custody/readback flow only. Missing historical evidence is not a blank result. Local adoption rejection retains successful captured evidence. No remote upload exists in this work.
- `S02` Shared dirty worktree contains concurrent unrelated changes; no commit or unrelated rollback performed. Existing S01 repository-wide type/import-boundary gaps remain.
