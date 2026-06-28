---
tags:
  - '#exec'
  - '#secure-storage-production-hardening'
date: '2026-05-27'
modified: '2026-05-27'
step_id: 'S314'
related:
  - '[[2026-05-22-secure-storage-production-hardening-refactor-plan]]'
  - '[[2026-05-27-secure-storage-diagnostics-profile-closeout-audit]]'
---

# `secure-storage-production-hardening` `W12.P26.S314`

Closed the diagnostics entrypoint secure-object row.

## Changes

- Localized the engineer-only diagnostics root help through `tr()`.
- Verified the module only registers `python -m aeat.diagnostics` subcommands and does not expose retired operator command paths.

## Tests

- `uv run ruff check src/aeat/diagnostics/__main__.py src/aeat/diagnostics/secure_objects.py src/aeat/diagnostics/profile.py src/aeat/diagnostics/test_secure_objects.py src/aeat/diagnostics/test_profile.py src/aeat/entrypoints/cli/test_config_setter.py`
- `uv run pytest src/aeat/diagnostics/test_secure_objects.py src/aeat/diagnostics/test_profile.py src/aeat/entrypoints/cli/test_config_setter.py -q`
- `uv run python -m aeat.locales audit`
