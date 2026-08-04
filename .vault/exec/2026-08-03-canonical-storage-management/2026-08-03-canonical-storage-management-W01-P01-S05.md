---
tags:
  - '#exec'
  - '#canonical-storage-management'
date: '2026-08-03'
modified: '2026-08-03'
body_schema: 'body-v1'
body_hash: 'sha256:6adc8890986ef43f3b6181b6ec71301820087050ef375fe2123fe82dfb05bd4b'
step_id: 'S05'
related:
  - "[[2026-08-03-canonical-storage-management-plan]]"
---

# Declare STORAGE_TAXONOMY as the single mapping keyed by StorageCategory with each subpath copied verbatim from the shipped table, gated by a test asserting the mapping is total over the enum

## Scope

- `src/cadrumo/core/_storage_taxonomy.py`

## Description

- Declare `STORAGE_TAXONOMY` as the single mapping keyed by `StorageCategory`, each subpath copied verbatim from the shipped table.

## Outcome

Landed in commit `08c61859c0`. Gated by `test_the_taxonomy_is_total_over_the_category_enum` (`set(STORAGE_TAXONOMY) == set(StorageCategory)`).

## Notes
