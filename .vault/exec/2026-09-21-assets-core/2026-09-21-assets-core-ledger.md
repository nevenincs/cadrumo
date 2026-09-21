---
tags:
  - '#exec'
  - '#assets-core'
date: '2026-09-21'
modified: '2026-09-21'
body_schema: 'body-v2'
body_hash: 'sha256:3c720094dd4d1c12db9726fa08ef738884f45591dc03f8198f3af0a4bb7df9a2'
related:
  - "[[2026-09-21-assets-core-plan]]"
---

# `assets-core` ledger

## Changes

- `S02` `M` `src/cadrumo/application/aggregation/tests/test_renta_ledger.py`
- `S02` `M` `src/cadrumo/application/aggregation/tests/test_inventory_source.py`
- `S02` `verify:` `uv run ruff check two P01.S02 test files` -> `pass`
- `S02` `by:` `assets-stage1-regression`
- `S01` `M` `.vault/reference/2026-09-21-assets-core-ownership-contracts-reference.md`
- `S01` `M` `.vault/research/2026-09-21-assets-core-lifecycle-and-integration-research.md`
- `S01` `M` `.vault/adr/2026-09-21-assets-core-lifecycle-contract-adr.md`
- `S01` `verify:` `vaultspec assets-core focused checks` -> `pass`
- `S01` `by:` `root`
- `S03` `A` `src/cadrumo/domain/renta/actividad_asset/`
- `S03` `A` `src/cadrumo/_data/registry/aeat/modelos/100/revisions/2025/parameters/0002-activity-asset-amortization.toml`
- `S03` `A` `dev/registry/tests/test_modelo_100_activity_asset_amortization_parameters.py`
- `S03` `A` `.vault/adr/2026-09-21-assets-core-cost-basis-stages-adr.md`
- `S03` `verify:` `Ruff ty basedpyright` -> `pass`
- `S03` `by:` `OpenAI GPT-5 lead; Terra High domain worker; Terra Max authority audit`
- `S04` `A` `src/cadrumo/application/actividad_asset/`
- `S04` `A` `src/cadrumo/adapters/persistence/profile/actividad_asset.py`
- `S04` `A` `src/cadrumo/adapters/persistence/profile/tests/test_actividad_asset_history.py`
- `S04` `M` `src/cadrumo/adapters/persistence/storage/secure_object_namespaces.py`
- `S04` `M` `src/cadrumo/adapters/persistence/storage/namespace_registry.py`
- `S04` `M` `src/cadrumo/adapters/persistence/storage/tests/test_namespace_registry.py`
- `S04` `verify:` `global namespace order test` -> `fail`
- `S04` `by:` `OpenAI GPT-5 lead; Terra High persistence worker`
- `S03` `verify:` `uv run pytest -n 0 -m integration dev/registry/tests/test_authoring_candidate_inspection.py` -> `pass`
- `S03` `verify:` `focused asset domain and authority pytest (13 tests)` -> `pass`
- `S04` `verify:` `focused combined P02 pytest (20 tests)` -> `pass`
- `S04` `verify:` `Ruff ty basedpyright git diff --check` -> `pass`

## Notes

- `S04` Global namespace-order tripwire reaches an unrelated concurrent income-lane omission: withholding_workflow is enrolled but absent from that lane's expected tuple. Assets expected-order entry is present.
