---
tags:
  - '#exec'
  - '#canonical-storage-management'
date: '2026-08-03'
modified: '2026-08-03'
body_schema: 'body-v1'
body_hash: 'sha256:677fefc9057d72e1567993193a4212c677849b6e8cebfffdbab385a662964def'
step_id: 'S97'
related:
  - "[[2026-08-03-canonical-storage-management-plan]]"
---

# Re-point the config reset repository's root resolution onto effective_storage_root once S10 lands, deleting the inline override-or-settings-default duplicate

## Scope

- `src/cadrumo/application/_config_reset_repository.py`

## Description

- Confirm the `ConfigResetJournalRepository` gating test suite is green before touching the file.
- Re-point `__init__`'s root resolution onto `effective_storage_root(storage_root, settings=settings)`, deleting the inline `settings or load_settings()` / `storage_root or resolved_settings....` duplicate and the now-unused `load_settings` import.
- Re-run the gating suite; note an unrelated peer-owned collateral failure in a broader collateral run (traced into in-flight debug scaffolding in `core/logging.py`, not touched by this change and not reproducible in isolation) and exclude it from this Step's scope per full-tree-gate ownership discipline.

## Outcome

Landed in commit `2c4cde0ce6`. Gated by `test_config_reset_repository.py` (12 tests, green before and after). Behaviour change: an explicit `storage_root` override was previously returned completely unnormalised; it is now normalised through the shared accessor.

## Notes

A broader collateral run over `test_config_reset_concurrency.py` / `test_config_reset_recovery.py` showed intermittent failures traced to in-flight peer debug scaffolding in `core/logging.py` (a `_dbgsys.stderr.write` call reachable from `configure_logging()`), unrelated to this Step's file and not present in isolated re-runs. Not fixed here — out of scope and owned by another lane.
