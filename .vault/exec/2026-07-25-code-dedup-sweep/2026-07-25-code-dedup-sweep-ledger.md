---
tags:
  - '#exec'
  - '#code-dedup-sweep'
date: '2026-07-25'
modified: '2026-08-26'
body_schema: 'body-v2'
body_hash: 'sha256:177d8edc8cc96025805f68ab7a7512639e55d714a09286e29800029305dfc917'
related:
  - "[[2026-07-25-code-dedup-sweep-plan]]"
---

# `code-dedup-sweep` ledger

## Changes

- `S01` `T` `src/cadrumo/adapters/persistence/storage/`
- `S02` `T` `10 sites in adapters/persistence/profile/`
- `S02` `T` `4 in adapters/outbound/aeat/sede/_observation_store.py`
- `S02` `T` `2 in application/workflow/_persistence.py`
- `S02` `T` `2 in application/user_profile/_repository.py`
- `S02` `T` `application/live/_verify.py`
- `S02` `T` `application/live/_snapshot_base.py`
- `S03` `T` `src/cadrumo/adapters/persistence/storage/tests/`
- `S04` `T` `src/cadrumo/adapters/persistence/storage/tests/test_schema_lineage.py`
- `S05` `T` `src/cadrumo/adapters/persistence/storage/_schema_lineage.py`
- `S06` `T` `storage/bucket/_manifest.py`
- `S06` `T` `storage/bucket/_manifest_io.py`
- `S06` `T` `application/user_profile/_profile_repository.py`
- `S06` `T` `new ADR`
