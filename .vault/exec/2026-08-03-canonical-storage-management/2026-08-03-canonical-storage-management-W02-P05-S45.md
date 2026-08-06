---
tags:
  - '#exec'
  - '#canonical-storage-management'
date: '2026-08-03'
modified: '2026-08-04'
body_schema: 'body-v1'
body_hash: 'sha256:67f1e1d2e9f2da36261e851105d3772f80ba772f8c187c12e345af339e265fa5'
step_id: 'S45'
related:
  - "[[2026-08-03-canonical-storage-management-plan]]"
---

# Declare the registry disk-cache resolver's pytest-shared temporary branch as an explicit test-pinned exception on the member rather than an undeclared special case, gated by a test asserting the declaration exists and the branch still selects under pytest

## Scope

- `src/cadrumo/domain/calculations/registry/_loader_cache.py`

## Description

## Outcome

Landed in `28179b95dc`, confirmed at HEAD. `REGISTRY_DISK_CACHE`'s declaration in `src/cadrumo/core/_storage_taxonomy_locations.py:343-358` carries an explicit `test_pinned_exception` field describing exactly the pytest-shared-directory branch (`domain/calculations/registry/_loader_cache.py`'s `_running_under_pytest()` check at line 156). Gated by `domain/calculations/registry/tests/test_registry_disk_cache_location.py`, which asserts both the declaration exists and the branch still selects the shared directory under pytest.

## Notes
