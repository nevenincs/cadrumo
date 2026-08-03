---
tags:
  - '#exec'
  - '#canonical-storage-management'
date: '2026-08-03'
modified: '2026-08-03'
body_schema: 'body-v1'
body_hash: 'sha256:a056ce9212710f9cc867c91541244fe8698d3dca6897e3a687b5d6fc80856961'
step_id: 'S44'
related:
  - "[[2026-08-03-canonical-storage-management-plan]]"
---

# Govern the registry disk-cache name through a taxonomy member while leaving the field itself un-derived by the settings validator, gated by a test asserting the production branch resolves to the taxonomy subpath and the field default stays absent

## Scope

- `src/cadrumo/domain/calculations/registry/_loader_cache.py`

## Description

- Add `StorageCategory.REGISTRY_DISK_CACHE` naming `cache/registry` in `STORAGE_TAXONOMY`, marked `derives_settings_default=False`.
- Leave `cadrumo_registry_disk_cache_dir` un-derived by the settings validator so its three-branch resolver keeps selecting on the field defaulting to `None`.

## Outcome

Landed in commit `3ee34dc721`. The category name is taxonomy-governed while the field's `None`-default pytest branch is preserved, per ADR R17.

## Notes
