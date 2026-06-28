---
tags:
  - '#exec'
  - '#secure-storage-production-hardening'
date: '2026-06-05'
modified: '2026-06-05'
step_id: 'S391'
related:
  - '[[2026-05-22-secure-storage-production-hardening-refactor-plan]]'
---

# W12.P26.S391 - Close AFR-289 for CLI TTY helpers

Scope: close `AFR-289` for `src/aeat/entrypoints/cli/_tty.py` with signal
`remote-provider`, target `remote-mirror`, and owner `W12.P24.S98`.

## Description

- Audited `_tty.py` as the centralized CLI TTY, colour, progress, and non-interactive
  stdin helper module.
- Confirmed environment-derived colour decisions are routed through `Settings` fields
  (`no_color`, `aeat_force_color`) rather than direct `os.environ` reads.
- Confirmed the module performs no secure-object access, active-profile discovery,
  manifest scanning, repository construction, remote IO, or persistence.
- Confirmed `NonTtyRefusedError` derives from the core AEAT error hierarchy and is
  declared in the centralized error registry.
- Wrapped generated profile `create` and `edit` wizard callbacks with the shared CLI
  error boundary so direct `profile_app` invocations render typed non-TTY refusals.
- Updated a stale profile-create recovery assertion from the deprecated `--tax-id NIF`
  placeholder to the current `DNI/NIE/NIF/CIF` operator guidance.
- Closed `W12.P26.S391` through `vaultspec-core vault plan step check` and updated the
  `AFR-289` register status to `closed`.

## Outcome

`AFR-289` is closed as `remote-mirror`. `_tty.py` remains a process/terminal boundary:
it observes local TTY state and centralized settings only, while storage and remote
provider concerns stay outside this module.

Validation passed:

- `uv run --no-sync ruff check src/aeat/entrypoints/cli/_tty.py src/aeat/entrypoints/cli/tests/test_tty_error_locale.py src/aeat/core/errors/registry/_application.py src/aeat/core/config.py`
- `uv run --no-sync pytest -q -m integration src/aeat/entrypoints/cli/tests/test_tty_error_locale.py`
- `uv run --no-sync pytest -q -m integration src/aeat/entrypoints/cli/tests/test_profile_lifecycle_verbs.py`
- `uv run --no-sync pytest -q src/aeat/core/errors/tests/test_registry_enforcement.py src/aeat/core/errors/tests/test_registry.py`
- `uv run --no-sync -q python -m aeat.locales audit`

## Notes

The `_tty.py` implementation itself required no change. Validation exposed adjacent
generated-wizard callback drift: direct `profile_app` tests bypass the root app's error
boundary, so `profile edit` non-TTY refusals escaped without rendered guidance. The
generated callbacks are now boundary-wrapped at registration. The current shared
worktree still carries unstaged cross-period clean-state locale/source work owned by its
own plan; the S391 validation was run against the current worktree and the locale audit
passed.
