---
tags:
  - '#audit'
  - '#secure-storage-production-hardening'
date: '2026-06-05'
modified: '2026-06-05'
related:
  - '[[2026-05-22-secure-storage-production-hardening-refactor-plan]]'
  - '[[2026-06-05-secure-storage-production-hardening-W12-P26-S391]]'
---

# `secure-storage-production-hardening` `W12.P26.S391` Review

## S391-001 | PASS | TTY helpers have no storage authority

Reviewed the S391 scope as `vaultspec-code-reviewer`. `_tty.py` checks `sys.stdin`,
`sys.stdout`, and `sys.stderr` TTY state and returns rendering decisions. It does not
open secure-object repositories, resolve active profiles, inspect manifests, read raw
environment variables, persist data, or call remote providers.

## S391-002 | PASS | Environment-derived flags are centralized through settings

Colour resolution uses `Settings.no_color` and `Settings.aeat_force_color` plus the
active CLI flag context. The module does not duplicate environment parsing and does not
read `NO_COLOR` or `AEAT_FORCE_COLOR` directly.

## S391-003 | PASS | Non-TTY refusal is registry-backed

`NonTtyRefusedError` derives from `AeatError`, carries no positional message args, and
is registered with `REFUSED_CLI_NON_TTY` in the centralized error registry. Locale
coverage for the registry message key is covered by the focused integration test.

## S391-004 | FIXED | Direct profile wizard callbacks bypassed error rendering

The focused profile lifecycle check exposed that `profile_app` direct invocations of the
generated `create`/`edit` wizard callbacks bypassed the root app's error boundary. The
callbacks are now registered through `command_error_boundary`, so a non-TTY `profile
edit` refusal renders the edit-specific recovery hint instead of returning empty output.

## S391-005 | FIXED | Profile-create recovery assertion used deprecated tax-id placeholder

The current localized recovery command uses `--tax-id DNI/NIE/NIF/CIF`. A profile
lifecycle test still expected the deprecated `--tax-id NIF` placeholder and now asserts
the current operator guidance.

## S391-006 | PASS | Validation

Focused ruff passed for `_tty.py`, its locale tests, the application error registry, and
settings. The TTY integration tests passed with 4 selected tests. Profile lifecycle
integration tests passed with 43 selected tests. Error-registry tests passed with 14
selected tests. The locale audit passed through `python -m aeat.locales audit`.

Reviewer note: no critical, high, medium, or low findings remain for the S391 slice.

Disposition: close `AFR-289` as `remote-mirror`.
