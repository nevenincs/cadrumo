---
tags:
  - '#exec'
  - '#secure-object-integrity'
date: '2026-05-22'
modified: '2026-05-22'
step_id: 'S10'
related:
  - '[[2026-05-22-secure-object-integrity-attribution-plan]]'
---




# `secure-object-integrity` `P03.S10`

Added real-entrypoint regression coverage for root-fallback write refusal and bootstrap-safe read probes.

- Created: `src/aeat/entrypoints/cli/test_root_fallback_write_guard.py`

## Description

The new test module runs CLI dispatch inside a subprocess with an argv shape equivalent to a real `aeat` console invocation. Each child process installs a real `Settings` object with `_env_file=None`, a fresh storage root, no active profile, and no explicit database URL, then asserts the effective route is `ROOT_FALLBACK_DATABASE` before calling `aeat.entrypoints.cli.main()`.

The coverage proves guarded profile-bound mutation verbs refuse before creating the root fallback database, while bootstrap-safe help, repair attribution, registry read probes, and profile-switch recovery remain open. Additional direct predicate checks cover mutation paths surfaced during S09 review and sampled read/recovery paths that must remain unguarded.

## Tests

Focused gates passed:

- `uv run ruff check src/aeat/entrypoints/cli/test_root_fallback_write_guard.py src/aeat/entrypoints/cli/__init__.py`
- `uv run pytest src/aeat/entrypoints/cli/test_root_fallback_write_guard.py`

Review audit: `2026-05-22-secure-object-integrity-P03-S10-review`.
