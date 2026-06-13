---
tags:
  - '#exec'
  - '#secure-storage-production-hardening'
date: '2026-05-27'
modified: '2026-05-27'
step_id: 'S93'
related:
  - '[[2026-05-22-secure-storage-production-hardening-refactor-plan]]'
---



# `secure-storage-production-hardening` `W12.P23.S93` Output Language Fixture Slice

Closed a focused S93 test-fixture migration for output-language surfaces without touching concurrent workflow, modelo, profile lifecycle, locale, or fixture changes in the shared worktree.

## Changes

- Migrated profile-owned output-language tests from manual environment/database setup to `isolated_profile_storage_root` plus `profile_create_storage_span`.
- Replaced direct `AEAT_OUTPUT_LANGUAGE` mutation in the migrated tests with centralized `override_settings(aeat_output_language=...)`.
- Migrated output-language CLI help parity tests from local `override_settings` and direct engine disposal to `isolated_sessionless_storage_root`.
- Tightened the CLI help parity assertion so each target command must expose both `--output-language` and the constrained shared language choice list derived from `SUPPORTED_OUTPUT_LANGUAGES`.

## Validation

- `uv run pytest -q src/aeat/core/i18n/test_output_language.py src/aeat/entrypoints/cli/test_output_language_parity.py src/aeat/entrypoints/cli/test_config_setter.py src/aeat/entrypoints/cli/test_audit_verbs.py` - 31 passed.
- `uv run ruff check src/aeat/core/i18n/test_output_language.py src/aeat/entrypoints/cli/test_output_language_parity.py` - passed.
- `rg -n "AEAT_DATABASE_URL|AEAT_LOCAL_STORAGE_ROOT|monkeypatch\\.setenv|aeat_database_url|EphemeralMasterKeyProvider|create_engine_from_settings" ...output-language slice...` - no hits in the touched files.

## Tracking

Completed internal tasklist for this slice:

- Identify clean S93 candidate tests with manual route or settings setup: complete.
- Replace manual storage/env setup with sanctioned secure SQL helpers: complete.
- Preserve sessionless CLI help behavior without activating a bucket session: complete.
- Resolve review finding on constrained language-choice assertion: complete.
- Persist focused execution evidence: complete.

S93 remains open because the row covers the broader test/runtime helper migration across the project.
