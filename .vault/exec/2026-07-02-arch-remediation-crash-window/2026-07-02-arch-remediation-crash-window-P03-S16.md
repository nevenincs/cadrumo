---
tags:
  - '#exec'
  - '#arch-remediation-crash-window'
date: '2026-07-02'
modified: '2026-07-17'
step_id: 'S16'
related:
  - "[[2026-07-02-arch-remediation-crash-window-plan]]"
---

# Assert the sealed-archive writer checkpoints or includes the -wal sidecar so a sealed bundle carries every committed row

## Scope

- `src/aeat/adapters/persistence/storage/tests/test_wal_sidecar_accounting.py`

## Description

Authored the sealed-export WAL-sidecar accounting test: write a real committed-but-uncheckpointed row and prove the SQL read layer (the layer `serialize_profile_bundle` uses to build the sealed-archive payload) returns the row even though the raw main `.db` file does not yet carry it, so a sealed bundle carries every committed row regardless of checkpoint state.

## Outcome

One test passes: the sealed export inherits the SQL read layer's WAL visibility, so no committed row is dropped.

## Notes

Tested at the SQL-read layer rather than through the export service, which is transiently blocked by an unrelated peer import break in `domain.user_profile`.
