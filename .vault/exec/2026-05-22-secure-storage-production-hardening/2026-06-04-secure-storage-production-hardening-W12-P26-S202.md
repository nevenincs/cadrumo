---
tags:
  - '#exec'
  - '#secure-storage-production-hardening'
date: '2026-06-04'
modified: '2026-06-04'
step_id: 'S202'
related:
  - '[[2026-05-22-secure-storage-production-hardening-refactor-plan]]'
  - '[[2026-06-04-secure-storage-production-hardening-w12-p26-s202-review-audit]]'
---

# `secure-storage-production-hardening` `W12.P26.S202`

Closed `AFR-100` for config reset.

## Description

- Reviewed `src/aeat/application/config_reset.py` against the
  `runtime-default` classification for secure-object, manifest-bucket, and SQL
  route behavior.
- Added the registered translated-message key to
  `ConfigResetUnconfirmedError`, removed the raw fallback message, and carried
  the refused scope as structured context.
- Extended `test_config_reset.py` to assert the application error carries the
  registered locale key, structured context, and localized envelope message
  without assuming the process output language is English.
- Added `reset_config(..., confirmed=True)` for AUTH, PROFILE, DATA, and ALL
  scopes to the runtime migration missing-session and route/session-mismatch
  refusal matrices.

## Outcome

`AFR-100` is closed. Config reset continues to operate through the active bucket
workflow-state runtime route, profile manifest/lifecycle repositories, and the
diagnostics quarantine pipeline, and it now has explicit runtime refusal coverage
for every reset scope plus registry-rendered translated-message metadata on its
application-level confirmation refusal. The refusal no longer depends on a raw
English exception string.

Validation passed:

- `uv run --no-sync ruff check src/aeat/application/config_reset.py src/aeat/application/test_config_reset.py src/aeat/adapters/persistence/storage/test_runtime_migrated_repositories.py`
- `$env:PYTHONPATH='src'; uv run --no-sync -q pytest -q src/aeat/application/test_config_reset.py src/aeat/adapters/persistence/storage/test_runtime_migrated_repositories.py -k "config_reset"`
- `$env:PYTHONPATH='src'; uv run --no-sync -q python -m aeat.locales audit`

## Notes

No locale catalogue changes were needed for S202. No direct secure-object
repository construction, naked environment access, silent exception swallowing,
raw user-facing strings, `noqa`, `pragma`, monkeypatches, fakes, mocks, skips, or
xfails were introduced.
