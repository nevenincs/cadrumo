---
tags:
  - '#exec'
  - '#semantic-consolidation'
date: '2026-08-30'
modified: '2026-08-30'
body_schema: 'body-v2'
body_hash: 'sha256:ab5450c87211abcdc2209fd89798c4bffa3b1aba910550b4ece9e3f868b23a87'
step_id: 'S114'
related:
  - "[[2026-08-28-semantic-consolidation-plan]]"
---

# Publicise the secret store's defining module, which the inert namespace left unreachable for its blob-store and storage consumers

## Scope

- `src/cadrumo/adapters/persistence/storage/secret_store/`

## Changes

- `R` `src/cadrumo/adapters/persistence/storage/secret_store/_secret_store.py -> store.py`
- `M` 8 consumers
- `verify:` `pytest src/cadrumo/adapters/persistence/storage/secret_store -n 0 -m ""` -> `pass` (59)

## Notes

The namespace had been made inert while four sites still reached through it,
including production `blob_store/_materialisation.py` and the storage lazy map.
Collection failed for 1544 tests until the defining module was public.
