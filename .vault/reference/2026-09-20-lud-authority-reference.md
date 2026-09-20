---
tags:
  - '#reference'
  - '#lud-authority'
date: '2026-09-20'
modified: '2026-09-20'
body_schema: 'body-v2'
body_hash: 'sha256:a1a3d89b1b3b859c75a0ea3161e0ea1d37626ac0816fd905cec4e833cdbb8d80'
related: []
---



# `lud-authority` reference: `startup provisioning and authority loading`

Current-tree reference at commit `81a3943c0fec468822fd6c55fa6a0b6233032e9f`. The inspection followed normal CLI startup from settings resolution through storage materialization and published-authority selection, then checked the focused tests and configuration gates that constrain a change.

## Summary

Normal settings construction computes paths but performs no I/O. Root-derived output locations are assigned only when their settings fields are absent from `model_fields_set`; explicit environment and in-process overrides remain distinguishable after resolution. See `src/cadrumo/core/_config_validation.py:123` and `src/cadrumo/core/_config_validation.py:157`.

`ensure_storage_tree()` is the existing single materialization boundary. It walks the canonical taxonomy-derived target set, skips directories already present, rejects a file occupying a directory path through `CoreValidationError`, creates absent targets idempotently, and restricts the state-root permissions. It currently applies identical creation behavior to derived defaults and explicit per-field overrides. See `src/cadrumo/core/storage_materialization.py:20` and `src/cadrumo/core/storage_taxonomy_locations.py:870`.

The CLI entrypoint already separates metadata invocations from normal command startup and owns a typed startup-refusal projection. Normal commands perform the former-product-state preflight before dispatch; metadata calls use isolated temporary state and must remain independent of the operator's runtime directories. This is the narrow insertion point for a fast provisioning check. See `src/cadrumo/entrypoints/cli/main.py:127`, `src/cadrumo/entrypoints/cli/main.py:146`, and `src/cadrumo/entrypoints/cli/main.py:182`.

Published registry authority is selected through `bundled_authority_descriptor_path()`. An explicit `cadrumo_authority_root` is the whole answer and missing publication beneath it fails closed; when unset, resolution uses the shipped bundled-data boundary and likewise refuses an unavailable descriptor. Runtime does not compile or create authority. See `src/cadrumo/core/config.py:426`, `src/cadrumo/domain/calculations/registry/authority.py:939`, and `src/cadrumo/domain/calculations/registry/errors.py:104`.

The minimal extension is therefore within existing modules: teach the storage materializer to create only taxonomy-derived defaults while validating explicit directory overrides as pre-provisioned dependencies; compose that with canonical authority descriptor validation in the application provisioning surface; invoke it only for normal CLI commands through the existing startup refusal boundary. No new path setting, loader, cache list, or authority-generation path is needed.
