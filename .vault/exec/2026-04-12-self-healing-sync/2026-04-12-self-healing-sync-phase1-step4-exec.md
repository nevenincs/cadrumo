---
tags:
  - "#exec"
  - "#self-healing-sync"
date: 2026-04-12
modified: '2026-04-12'
related:
  - "[[2026-04-12-self-healing-sync-plan]]"
  - "[[2026-04-12-self-healing-sync-adr]]"
---

# step 4 — repository + validator

- `_repository.py` — `DivergenceRecordRepository` Protocol,
  `JsonFileDivergenceRepository` (atomic writes via temp + `os.replace`),
  and a rebase-swap `StorageDivergenceRepository` that refuses to
  construct until #10 merges.
- `_validator.py` (from step 1) satisfies the validator slot; wire
  tests already exercise it.
- `test_repository.py` — tmp_path round-trip, list, update resolution,
  missing-record error, and a storage-stub refusal assertion.

49 unit tests green.
