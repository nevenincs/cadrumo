---
tags:
  - '#exec'
  - '#canonical-storage-management'
date: '2026-08-03'
modified: '2026-08-03'
body_schema: 'body-v1'
body_hash: 'sha256:265a7345965484b432d81264ce36031a14862a096567b774010e953a46910f60'
step_id: 'S66'
related:
  - "[[2026-08-03-canonical-storage-management-plan]]"
---

# Delete the duplicate bare exclusion frozenset the taxonomy test had re-derived from the fingerprint module's old attribute reads, keeping the reasoned per-entry oracle as the sole statement of the excluded set, and replace the override-precedence test's self-referential comparison with a control Settings built without the override so the assertion proves displacement rather than a value equalling itself

## Scope

- `src/cadrumo/core/tests/test_storage_taxonomy.py`
- `src/cadrumo/core/tests/test_config_state_root.py`

## Description

- Delete the duplicate bare ten-name exclusion frozenset in the taxonomy test that had drifted from the fingerprint module's old attribute reads; keep the reasoned per-entry oracle in the participation gate as sole source of truth.
- Replace the override-precedence test's self-referential comparison (accessor vs. the field it reads first) with a control `Settings` built without the override, so "the override won" compares two independent resolutions.

## Outcome

Landed in commits `0b75cb5249` and `de02893d7e`.

## Notes
