---
tags:
  - '#audit'
  - '#aeat-cli-hardening'
date: '2026-05-08'
modified: '2026-05-08'
related:
  - '[[2026-05-08-aeat-cli-hardening-plan]]'
  - '[[2026-05-08-aeat-cli-hardening-inventory-audit]]'
---



# `aeat-cli-hardening` Code Review


## Review Pass 1: `A23` And `A27` Help Copy Drift

Scope reviewed: `src/aeat/entrypoints/cli/_setup.py`,
`src/aeat/entrypoints/cli/test_user_cli_surface.py`, and the locale files for
Spanish, English, Catalan, and Hungarian.

No CRITICAL, HIGH, MEDIUM, or LOW findings were identified in this slice.

Review notes:

- `auth reset` no longer carries inline English command or option help.
- The reset scope validation message now uses the locale catalogue.
- Invoice import `--kind` help now names the actual accepted CLI values.
- Tests invoke the real Typer app help surface and can fail if the old wording
  returns.
- No business logic was added to CLI handlers; the change is restricted to
  existing command metadata and tests.

## Review Pass 2: `A3` Version Surface

Scope reviewed: `src/aeat/application/diagnostics.py`,
`src/aeat/entrypoints/cli/__init__.py`,
`src/aeat/entrypoints/cli/test_user_cli_surface.py`, and the locale files for
Spanish, English, Catalan, and Hungarian.

No CRITICAL, HIGH, MEDIUM, or LOW findings were identified in this slice.

Review notes:

- Registry summary construction lives in the application layer, not the root
  command handler.
- The CLI renders a typed backend report and does not count registry TOMLs.
- `--version`, `-V`, `version`, and `--format json version` are all covered by
  real Typer invocation.
- The first implementation failed for `--version` and `-V` because Typer did
  not invoke the callback without a command. The final implementation sets the
  root group to invoke the callback without a command while preserving
  no-argument help behavior.

## Review Pass 3: `DISCOVERED-006` Setup Status Boundary

Scope reviewed: `src/aeat/application/setup_status.py`,
`src/aeat/application/test_setup_status.py`, and
`src/aeat/entrypoints/cli/_setup.py`.

No CRITICAL, HIGH, MEDIUM, or LOW findings were identified in this slice.

Review notes:

- Setup readiness and next-action projection now live in an application-layer
  typed report.
- The CLI handler delegates to the backend service and renders the returned
  fields without recomputing readiness.
- Backend tests cover each current next-action branch using real domain and
  application models.
- The first verification pass exposed that `profile validate` still needed the
  existing `validate_profile` import; the repair restored that import without
  moving profile validation logic back into `setup status`.
