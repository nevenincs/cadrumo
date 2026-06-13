---
tags:
  - '#exec'
  - '#aeat-cli-hardening'
date: '2026-05-08'
modified: '2026-05-08'
related:
  - '[[2026-05-08-aeat-cli-hardening-plan]]'
---



# `aeat-cli-hardening` `W6 Error Surface` `Startup Import Error`

Closed the startup import-error slice after the config-scoped doctor surface
was available.

- Modified: `src/aeat/entrypoints/cli/__init__.py`
- Modified: `src/aeat/entrypoints/cli/test_user_cli_surface.py`
- Modified: `2026-05-08-aeat-cli-hardening-plan.md`

## Description

The root CLI now imports the config facade before the heavier setup and app
namespaces. If a setup or app namespace import fails because a required module
is missing, the CLI registers a placeholder surface that emits a short
operator-facing diagnostic with `aeat config doctor` as the recovery command.

The import guard intentionally does not register root `aeat doctor` and does
not expose a Python traceback for the missing-dependency failure path.

## Tests

Verification commands:

- `uv run --no-sync pytest src/aeat/entrypoints/cli/test_user_cli_surface.py -k "startup_import_failure or root_surface or removed_developer or config_doctor"`
- `uv run --no-sync ruff check src/aeat/entrypoints/cli/__init__.py src/aeat/entrypoints/cli/test_user_cli_surface.py`
- `uv run --no-sync ruff format --check src/aeat/entrypoints/cli/__init__.py src/aeat/entrypoints/cli/test_user_cli_surface.py`
- `uv run --no-sync ty check src/aeat/entrypoints/cli/__init__.py`

All verification commands passed.
