---
step_id: S56
date: 2026-05-31
modified: '2026-05-31'
tags:
  - "#exec"
  - "#core-authority"
related:
  - "[[2026-05-31-core-authority-plan]]"
  - "[[2026-05-31-core-authority-adr]]"
---

# core-authority W06.P17.S56

## Summary

Added a CI-gate isinstance test asserting `SnapshotRepository` structural conformance for all three concrete live snapshot repositories. `SnapshotRepository` already carried `@runtime_checkable`; no changes to the Protocol itself were needed.

## Changes

`src/aeat/application/live/test_snapshot_base.py`: Added 4 new tests to the existing snapshot base test file:

- `test_borrador100_snapshot_repository_conforms_to_protocol`: asserts `isinstance(Borrador100SnapshotRepository(...), SnapshotRepository)` and that `SnapshotRepository not in type(repo).__mro__` (Rule 9-A: structural only, no explicit inheritance)
- `test_censo_snapshot_repository_conforms_to_protocol`: asserts `isinstance(CensoSnapshotRepository(...), SnapshotRepository)`
- `test_secure_snapshot_repository_conforms_to_protocol`: constructs `SecureSnapshotRepository[PersistedExpedientesSnapshot]` directly and asserts isinstance
- `test_snapshot_repository_protocol_anti_tautology`: proves the gate is real — a `NotARepo` class with no matching members is NOT accepted

## Test Results

4 new tests pass. Full test_snapshot_base.py suite (30 tests) passes.

## Commit

`339b3f60a` — test(live): W06.P17.S56 - SnapshotRepository structural conformance gate
