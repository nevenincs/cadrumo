---
tags:
  - '#exec'
  - '#binding-schema'
date: '2026-09-12'
modified: '2026-09-12'
body_schema: 'body-v2'
body_hash: 'sha256:20c570ebe38a79d4b32fcf0ec8f38c7c8b1c6cfd6d46fd0d5506ee13b0ce4f8d'
step_id: 'S09'
related:
  - "[[2026-09-11-binding-schema-plan]]"
---

# Narrow ledger, oss, inventory, foreign-asset, service, profile and filing readers on typed provider members

## Scope

- `src/cadrumo/application/aggregation/inventory.py`
- `src/cadrumo/application/aggregation/foreign_assets.py`
- `src/cadrumo/application/calculations/foreign_asset_redeclaration.py`
- `src/cadrumo/application/aggregation/oss_ioss.py`
- `src/cadrumo/application/aggregation/modelo_bindings.py`
- `src/cadrumo/application/aggregation/iva_ledger.py`
- `src/cadrumo/application/aggregation/service.py`
- `src/cadrumo/application/modelo/profile_binding.py`
- `src/cadrumo/application/filing/runtime.py`
- `src/cadrumo/application/filing/draft_construction.py`

## Changes

- `M` `src/cadrumo/application/aggregation/inventory.py`
- `M` `src/cadrumo/application/aggregation/oss_ioss.py`
- `M` `src/cadrumo/application/aggregation/service.py`
- `M` `src/cadrumo/application/aggregation/iva_ledger.py`
- `M` `src/cadrumo/application/aggregation/modelo_bindings.py`
- `M` `src/cadrumo/application/calculations/foreign_asset_redeclaration.py`
- `M` `src/cadrumo/application/modelo/profile_binding.py`
- `M` `src/cadrumo/application/modelo/_profile_export_binding.py`
- `M` `src/cadrumo/application/modelo/_revision_replay_inputs.py`
- `M` `src/cadrumo/application/modelo/_calculation_modelo_adjustments.py`
- `M` `src/cadrumo/application/modelo/borrador_binding.py`
- `M` `src/cadrumo/application/modelo/workspace_manifest.py`
- `M` `src/cadrumo/application/filing/runtime.py`
- `M` `src/cadrumo/application/filing/draft_construction.py`
- `M` `src/cadrumo/adapters/outbound/google/calc_sheets_pull.py`
- `M` `src/cadrumo/domain/user_profile/registry_contract.py`
- `verify:` `uv run ruff check <touched>` -> `pass`
- `verify:` `uv run ty check <touched>` -> `pass`
- `verify:` `uv run basedpyright <touched>` -> `pass`

## Notes

`aggregation/foreign_assets.py` already read its selector through the typed
row-set accessor and needed no change.

`workspace_manifest.py` lost its import of the deleted `selector_model_for_source`;
the selector traversal roots now derive from the provider enrollment table, which
excludes mesh-only source kinds by construction.

`inventory.py` guarded an authored `filing_year` the provider no longer carries.
The guard was re-expressed against the temporal selector, which is where that
invariant now lives.

`_calculation_modelo_adjustments.py` lost a dead `rectification_scope is None`
branch: the typed field is non-optional with a default.

`profile_binding_selectors` was narrowed to the provider union and its
Mapping-reading branch deleted, so the dual path is gone at its source.

Repository test suites for these modules cannot run: the published authority
artifact is mid-regeneration and fails validation in an autouse fixture.
