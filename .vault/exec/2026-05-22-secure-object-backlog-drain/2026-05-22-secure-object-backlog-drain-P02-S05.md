---
tags:
  - '#exec'
  - '#secure-object-backlog-drain'
date: '2026-05-22'
modified: '2026-05-22'
step_id: 'S05'
related:
  - '[[2026-05-22-secure-object-backlog-drain-plan]]'
---



# `secure-object-backlog-drain` `P02.S05`

Repaired the selected secure-SQL hygiene slice with settings-backed
isolation and shrank the classified exception map by three files.

- Modified: `src/aeat/adapters/outbound/aeat/sede/_observation_store.py`
- Modified: `src/aeat/adapters/outbound/aeat/sede/test_observation_store.py`
- Modified: `src/aeat/adapters/persistence/storage/test_submission_repository.py`
- Modified: `src/aeat/domain/usage_ratios/test_service.py`
- Modified: `src/aeat/adapters/persistence/storage/test_ephemeral_key_hygiene.py`
- Modified: `src/aeat/tests/secure_sql.py`
- Modified: `src/aeat/entrypoints/cli/test_repair_privacy_contract.py`
- Created: `.vault/exec/2026-05-22-secure-object-backlog-drain/2026-05-22-secure-object-backlog-drain-P02-S05.md`

## Description

Converted the three selected modules away from process environment
mutation. The repaired tests now either inject a `SecureObjectRepository`
backed by `create_engine_from_settings(Settings(aeat_database_url=...))`
or, for default-lookup helper coverage, use `override_settings` around
the in-process scope. The observation store gained an optional secure
object repository injection point so tests can exercise the real store
without relying on global database routing. The tests still use real
SQLite-backed secure-object persistence and the same business
assertions. Removed the three repaired modules from
`_PENDING_P02_S06_CLASSIFICATIONS`.

## Tests

`uv run ruff check` passed for the repaired modules and the hygiene
guard. A targeted search found no remaining `monkeypatch`,
`MonkeyPatch`, `setenv`, `AEAT_DATABASE_URL`, or `os.environ`
references in the touched secure-SQL slice, and none of the three
repaired paths remains in the pending classification map.
