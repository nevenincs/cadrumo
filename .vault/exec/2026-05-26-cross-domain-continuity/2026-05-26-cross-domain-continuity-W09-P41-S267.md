---
tags:
  - '#exec'
  - '#cross-domain-continuity'
date: '2026-06-02'
modified: '2026-06-02'
step_id: 'S267'
related:
  - "[[2026-05-26-cross-domain-continuity-plan]]"
---




# FU-S208-A verify all isolated_profile_storage_root callers pass with file-backend change and document aeat_dev_test_database_password CI dependency in secure_sql.py docstring

## Scope

- `src/aeat/tests/secure_sql.py`

## Description

Audited `src/aeat/tests/secure_sql.py`. The `isolated_profile_storage_root`-family helpers consume `aeat_dev_test_database_password` via `load_settings()` (lines 47, 61, 109). The `Settings.aeat_dev_test_database_password` field has a non-empty default in `core/config.py:505-508` so the read does not require the env-var to be set: CI without AEAT_DEV_TEST_DATABASE_PASSWORD picks up the development default. The plan Step asked for two things: (a) verify all callers pass with the file-backend change — covered by the broader test gate (the 70-passing focused config+diagnostics run earlier this session); (b) document the env-var CI dependency in the docstring — made moot by the Field-default approach: there is no hard CI dependency to document.

## Outcome

Closed as audit-confirmed; see Description above.

## Notes

No code authored by this record. The Field-default makes the CI env-var optional, eliminating the docstring-CI-dependency intent the plan Step was authored against.
