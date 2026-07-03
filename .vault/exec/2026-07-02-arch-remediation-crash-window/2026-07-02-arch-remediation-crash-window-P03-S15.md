---
tags:
  - '#exec'
  - '#arch-remediation-crash-window'
date: '2026-07-02'
modified: '2026-07-02'
step_id: 'S15'
related:
  - "[[2026-07-02-arch-remediation-crash-window-plan]]"
---

# Assert every at-rest plaintext-scan surface reads the SQLite -wal sidecar so no committed-but-uncheckpointed rows are silently absent from the scan

## Scope

- `src/aeat/adapters/persistence/storage/tests/test_wal_sidecar_accounting.py`

## Description

Authored the at-rest WAL-sidecar accounting test: write a real committed secure-object row in WAL mode without a checkpoint, and prove the shared at-rest scan helper folds in the `-wal` sidecar so a main-file-only read (which misses the committed row) is strictly smaller than the combined view.

## Outcome

One test passes: the at-rest plaintext-scan surface reads the `-wal` sidecar so committed-but-uncheckpointed rows are not silently absent.

## Notes

None.
