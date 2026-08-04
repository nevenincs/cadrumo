---
tags:
  - '#exec'
  - '#canonical-storage-management'
date: '2026-08-03'
modified: '2026-08-04'
body_schema: 'body-v1'
body_hash: 'sha256:db3d859650e93603fea457719a26e6630f705a8df0eff195d792b9410e20bbca'
step_id: 'S52'
related:
  - "[[2026-08-03-canonical-storage-management-plan]]"
---

# Re-point the validation-verdict cache read onto the accessor, gated by the existing verdict location test re-expressed against the taxonomy

## Scope

- `src/cadrumo/domain/calculations/registry/_validate_verdict.py`

## Description

## Outcome

Landed in `06eb40877b`, confirmed at HEAD. `src/cadrumo/domain/calculations/registry/_validate_verdict.py:174` returns `storage_path(StorageCategory.VALIDATION_VERDICT_CACHE) / f"..."` rather than reading `cadrumo_validation_verdict_cache_dir` directly. Gated by `domain/calculations/registry/tests/test_validation_verdict_location.py`.

## Notes
