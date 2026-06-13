---
tags:
  - '#exec'
  - '#secure-storage-production-hardening'
date: '2026-05-27'
modified: '2026-05-27'
step_id: 'S315'
related:
  - '[[2026-05-22-secure-storage-production-hardening-refactor-plan]]'
  - '[[2026-05-27-secure-storage-diagnostics-profile-closeout-audit]]'
---

# `secure-storage-production-hardening` `W12.P26.S315`

Closed the diagnostics profile manifest-discovery row.

## Changes

- Routed diagnostics `profile get/set/unset --profile NAME` through `profile_storage_session(pointer.bucket_id)`.
- Localized profile diagnostic help and Typer validation errors with `tr()` and locale leaves maintained through `python -m aeat.locales`.
- Added real-bucket regression coverage proving explicit `--profile` does not mutate the active bucket.

## Tests

- `uv run ruff check src/aeat/diagnostics/__main__.py src/aeat/diagnostics/secure_objects.py src/aeat/diagnostics/profile.py src/aeat/diagnostics/test_secure_objects.py src/aeat/diagnostics/test_profile.py src/aeat/entrypoints/cli/test_config_setter.py`
- `uv run pytest src/aeat/diagnostics/test_secure_objects.py src/aeat/diagnostics/test_profile.py src/aeat/entrypoints/cli/test_config_setter.py -q`
- `uv run python -m aeat.locales audit`
