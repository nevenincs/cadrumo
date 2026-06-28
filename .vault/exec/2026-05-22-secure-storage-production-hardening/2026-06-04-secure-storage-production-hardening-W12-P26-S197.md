---
tags:
  - '#exec'
  - '#secure-storage-production-hardening'
date: '2026-06-04'
modified: '2026-06-04'
step_id: 'S197'
related:
  - '[[2026-05-22-secure-storage-production-hardening-refactor-plan]]'
  - '[[2026-06-04-secure-storage-production-hardening-w12-p26-s197-review-audit]]'
---

# `secure-storage-production-hardening` `W12.P26.S197`

Closed `AFR-095` for auth diagnostics.

## Description

- Reviewed `src/aeat/application/auth/_diagnostics.py` against the
  `runtime-default` active-profile secure-object classification.
- Verified diagnostics use the active-bucket runtime repository factory.
- Replaced raw UTF-8 payload and fingerprint encoding literals with
  `UTF_8_ENCODING`.
- Updated diagnostics tests to use the shared encoding constant.
- Re-ran the existing runtime-default guard for `auth_diagnostics`.

## Outcome

`AFR-095` is closed. Auth diagnostics remain active-profile encrypted storage,
with centralized encoding constants and existing typed/redacted diagnostic
behavior preserved.

Validation passed:

- `uv run --no-sync ruff check src/aeat/application/auth/_diagnostics.py src/aeat/application/auth/test_diagnostics.py`
- `uv run --no-sync pytest -q src/aeat/application/auth/test_diagnostics.py`
- `uv run --no-sync pytest -q src/aeat/adapters/persistence/storage/test_runtime_migrated_repositories.py -k "migrated_runtime_defaults_refuse and auth_diagnostics"`
- `$env:PYTHONPATH='src'; uv run --no-sync -q python -m aeat.locales audit`

## Notes

No direct secure-object repository construction, settings bypass, naked
environment access, monkeypatches, fakes, mocks, skips, or xfails were
introduced.
