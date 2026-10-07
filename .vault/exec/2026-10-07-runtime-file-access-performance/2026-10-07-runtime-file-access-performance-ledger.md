---
tags:
  - '#exec'
  - '#runtime-file-access-performance'
date: '2026-10-07'
modified: '2026-10-07'
body_schema: 'body-v2'
body_hash: 'sha256:204f22da0abd4c28768edd546cccd618f2fb7f68708c18dbf485a6a008085811'
related:
  - "[[2026-10-07-runtime-file-access-performance-plan]]"
---

# `runtime-file-access-performance` ledger

## Changes

- `S01` `A` `dev/ci/runtime_file_access.py`
- `S01` `A` `dev/ci/tests/test_runtime_file_access.py`
- `S01` `M` `dev/quality/metadata/import_load_targets.dev.json`
- `S01` `M` `dev/quality/metadata/import_load_targets.json`
- `S01` `verify:` `pytest dev/ci/tests/test_runtime_file_access.py` -> `pass`
- `S01` `verify:` `just check-format` -> `pass`
- `S01` `verify:` `just check-style` -> `pass`
- `S01` `verify:` `just check-types` -> `pass`
- `S01` `verify:` `just check-import-boundaries` -> `pass`
- `S01` `verify:` `vaultspec-core vault plan check runtime-file-access-performance` -> `pass`
- `S01` `verify:` `vaultspec-core vault check all` -> `pass`
- `S02` `M` `src/cadrumo/application/modelo/local_observation_spreadsheet.py`
- `S02` `M` `src/cadrumo/adapters/inbound/financial/providers/xlsx.py`
- `S02` `M` `src/cadrumo/adapters/inbound/pdf/page_text_extraction.py`
- `S02` `M` `src/cadrumo/adapters/outbound/calculation_summary_pdf/summary_container.py`
- `S02` `M` `src/cadrumo/entrypoints/calculation_review_xlsx_operation_composition.py`
- `S02` `M` `src/cadrumo/entrypoints/reconciliation_export_operation_composition.py`
- `S02` `A` `src/cadrumo/entrypoints/tests/test_operation_registry_imports.py`
- `S02` `verify:` `pytest PDF extraction and local observation spreadsheet` -> `pass`
- `S02` `verify:` `pytest financial XLSX, PDF summary writer/verification, schema parity and spreadsheet composition` -> `pass`
- `S02` `verify:` `pytest fresh-process operation registry import guard` -> `pass`
- `S02` `verify:` `pytest runtime startup arguments` -> `pass`
- `S02` `verify:` `pytest headless runtime and operation composition -m ''` -> `pass`
- `S02` `verify:` `just check-format` -> `pass`
- `S02` `verify:` `just check-style` -> `pass`
- `S02` `verify:` `just check-types` -> `pass`
- `S02` `verify:` `just check-import-boundaries` -> `pass`
- `S01` `M` `dev/ci/runtime_file_access.py`
- `S01` `verify:` `just check-format` -> `pass`
- `S01` `by:` `Codex`
- `S02` `verify:` `pytest test_stock_openssl_verifies_the_signature_and_refuses_a_flipped_byte with explicit Git OpenSSL 3.5.7 PATH -m ''` -> `pass`
- `S02` `by:` `Codex`
- `S05` `M` `src/cadrumo/application/operator_surface/contract.py`
- `S05` `M` `src/cadrumo/application/modelo/source_policy.py`
- `S05` `M` `src/cadrumo/domain/calculations/registry/modelo_inception.py`
- `S05` `M` `src/cadrumo/domain/calculations/registry/tests/test_declared_inception_runtime_gate.py`
- `S05` `M` `dev/registry/pipeline/generated_tree_inventory.py`
- `S05` `M` `dev/registry/pipeline/render_check.py`
- `S05` `M` `dev/registry/pipeline/tests/test_generated_export_trees.py`
- `S05` `M` `dev/registry/tests/test_m390_annual_manual_worked_example.py`
- `S05` `M` `src/cadrumo/locales/es/docs.yml`
- `S05` `M` `src/cadrumo/locales/es/flows.yml`
- `S05` `M` `src/cadrumo/locales/en/docs.yml`
- `S05` `M` `src/cadrumo/locales/en/flows.yml`
- `S05` `M` `src/cadrumo/locales/ca/docs.yml`
- `S05` `M` `src/cadrumo/locales/ca/flows.yml`
- `S05` `M` `src/cadrumo/locales/hu/docs.yml`
- `S05` `M` `src/cadrumo/locales/hu/flows.yml`
- `S05` `A` `.vault/audit/2026-10-07-runtime-file-access-performance-broad-test-failure-brief-audit.md`
- `S05` `verify:` `pytest strict inception JSON and runtime gate plus two profile regressions` -> `pass`
- `S05` `verify:` `pytest all 13 reported calculation revision persistence failures` -> `pass`
- `S05` `verify:` `pytest action coverage and production assertions with CLI refusal targets` -> `pass`
- `S05` `verify:` `pytest historical export enrollment and unsupported source frame` -> `pass`
- `S05` `verify:` `pytest full source policy with all four languages` -> `pass`
- `S05` `verify:` `pytest all six M390 annual manual worked example checks` -> `pass`
- `S05` `verify:` `Ruff and format scoped S05 owners` -> `pass`
- `S05` `verify:` `just check-types` -> `pass`
- `S05` `verify:` `just check-data-format` -> `pass`
- `S05` `by:` `Codex`
- `S05` `verify:` `just check-format` -> `pass`
- `S05` `verify:` `just check-style` -> `pass`
- `S05` `verify:` `just check-import-boundaries on current shared source` -> `fail`
- `S04` `verify:` `just build-native Release bundle first incremental attempt` -> `fail`

## Notes

- `S01` Semantic RAG remains unavailable; profile caller identities and bounded defining-module reads provided discovery.
- `S01` Raw Process Monitor exports include process environments. Only target file operations were retained; raw exports and PML captures were deleted. One earlier tool output inadvertently included environment records.
- `S01` Native counters cover observed imports and admission; the capture lacks a process-exit record. ReadFile bytes are file API transfers, not physical media reads.
- `S01` Review correction: replace the unsafe unfiltered-export guidance with target file-operation filtering before export or inspection; no diagnostic behavior changed.
- `S02` The previously excluded `external_tool` signature test initially failed because OpenSSL was absent from PATH; an existing Git-bundled OpenSSL 3.5.7 was selected for the child test environment and the real verification/tamper refusal passed.
- `S05` The 157-case and 113-case reports cover different populations, totaling 270 distinct failed cases. Full inventory retained in the requested brief.
- `S05` The additional TUI probe remains 7 failed and 11 passed; together with the 9 passing policy tests, its combined run has 20 passed and 7 failed. These unrelated findings remain recorded for owning repair.
- `S05` The first S05 import check was invalidated by source changes with zero hard findings; a stable-source retry is running.
- `S05` Three current import runs loaded all 4522 modules with 15 kept contracts and zero hard findings, but concurrent governed source changes invalidate their overall verdict. Latest run 20261007T151810.433463Z-check-import-boundaries-58192-5c0a00ee remains unavailable. No gate weakened. S05 review pending this verification gap.
- `S04` First build started 2026-10-07T13:53:47.854695Z and ended 15:22:54.007971Z: 5342.08 wall seconds, 7803.31 descendant CPU seconds, shared source changed. Documentation compile failed after 5095 seconds on golden divergences and fixture resource cleanup; no bundle, ZIP or installed-artifact success claimed. Timings and logs retained at build/runtime-file-access/rebuild/build-timing.json and bundle.log.
- `S05` Final current-source import retry 20261007T152817.616073Z-check-import-boundaries-63064-612b3db4 also loaded all 4522 modules, kept all 15 contracts and found zero hard violations, but concurrent source changes invalidate the aggregate. Stop blind retries. S05 remains open pending a stable source check; its five repairs and complete failure brief are checkpointed with this explicit limitation.
