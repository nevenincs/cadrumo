---
tags:
  - '#exec'
  - '#canonical-storage-management'
date: '2026-08-03'
modified: '2026-08-03'
body_schema: 'body-v1'
body_hash: 'sha256:f8ad249038a651184f9a05c02a5ee4534351338b9ef48b0b65eaffad13235b1d'
step_id: 'S06'
related:
  - "[[2026-08-03-canonical-storage-management-plan]]"
---

# Add a transitional parity test asserting every key of the shipped derived-dirs dict has a taxonomy member whose subpath string is byte-identical, so the representation change cannot silently move a path

## Scope

- `src/cadrumo/core/tests/test_storage_taxonomy_parity.py`

## Description

- Add a transitional parity test asserting every key of the shipped derived-dirs dict has a taxonomy member with a byte-identical subpath.

## Outcome

Landed in commit `08c61859c0` as `test_storage_taxonomy_parity.py`. Retired later, outside this Step's scope, by commit `88c9faac4e` (the W03.P11 lifecycle-gate rewrite); its property was folded into `test_output_dir_state_root.py`'s hand-written oracle per ADR R20. `_STATE_ROOT_DERIVED_DIRS` itself still exists in `config.py` today as R20's sanctioned pinning oracle with a death date — its actual deletion is S17, still correctly unchecked.

## Notes
