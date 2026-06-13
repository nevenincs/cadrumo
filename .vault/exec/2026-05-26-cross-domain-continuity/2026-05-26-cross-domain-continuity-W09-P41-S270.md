---
tags:
  - '#exec'
  - '#cross-domain-continuity'
date: '2026-06-02'
modified: '2026-06-02'
step_id: 'S270'
related:
  - "[[2026-05-26-cross-domain-continuity-plan]]"
---




# FU-W09-A S267 verify CI sets AEAT_DEV_TEST_DATABASE_PASSWORD environment variable

## Scope

- `the cb51d03e7 commit changed isolated_profile_storage_root from EphemeralMasterKeyProvider to file backend + aeat_dev_test_database_password`
- `without the env-var 8+ existing callers (test_operator test_apex_workflow_verification test_config_reset test_diagnostics test_profile_repository) will fail at passphrase resolution`
- `.github/workflows/`

## Description

Audited the CI env-var requirement. AEAT_DEV_TEST_DATABASE_PASSWORD is OPTIONAL on CI: the `Settings.aeat_dev_test_database_password` field carries a Field(default=SecretStr(DEV_TEST_DATABASE_PASSWORD)) default in `core/config.py:505-508`, so unset env-var resolves to the in-process development password and every `isolated_profile_storage_root` caller resolves cleanly without CI intervention. The .github/workflows/ci.yml file deliberately keeps AEAT_LIVE_TESTS_ENABLED unset (per the comment on lines 6 and 90); the same hands-off posture is correct for the dev-test database password. No CI change required.

## Outcome

Closed as audit-confirmed; see Description above.

## Notes

No code authored by this record. The Field-default makes the CI env-var optional, eliminating the docstring-CI-dependency intent the plan Step was authored against.
