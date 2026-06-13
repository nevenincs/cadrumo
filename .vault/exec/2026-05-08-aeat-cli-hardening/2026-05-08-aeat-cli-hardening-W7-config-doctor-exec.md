---
tags:
  - '#exec'
  - '#aeat-cli-hardening'
date: '2026-05-08'
modified: '2026-05-08'
related:
  - '[[2026-05-08-aeat-cli-hardening-plan]]'
---



# `aeat-cli-hardening` `W7 Config Facade` `Config Doctor`

Closed the first diagnostics slice by implementing the doctor surface under the
config facade, not at the root.

- Modified: `src/aeat/application/diagnostics.py`
- Created: `src/aeat/application/test_diagnostics.py`
- Created: `src/aeat/entrypoints/cli/_config.py`
- Modified: `src/aeat/entrypoints/cli/__init__.py`
- Modified: `src/aeat/entrypoints/cli/test_user_cli_surface.py`
- Modified: `src/aeat/locales/es.yml`
- Modified: `src/aeat/locales/en.yml`
- Modified: `src/aeat/locales/ca.yml`
- Modified: `src/aeat/locales/hu.yml`
- Modified: `2026-05-08-aeat-cli-hardening-plan.md`

## Description

The diagnostics report is produced by the application diagnostics module. It
checks Python/package version, log path, registry load, secure state load,
profile readiness, and auth readiness. The CLI only renders the typed report
as text or JSON.

The root command remains free of `doctor`; `aeat config doctor` is the
diagnostic entrypoint and `aeat config doctor logs` exposes the configured log
file path and recent lines.

## Tests

Verification commands:

- `uv run --no-sync pytest src/aeat/application/test_diagnostics.py src/aeat/entrypoints/cli/test_user_cli_surface.py -k "config_doctor or root_surface or root_no_args or removed_developer"`
- `uv run --no-sync ruff check src/aeat/application/diagnostics.py src/aeat/application/test_diagnostics.py src/aeat/entrypoints/cli/_config.py src/aeat/entrypoints/cli/__init__.py src/aeat/entrypoints/cli/test_user_cli_surface.py`
- `uv run --no-sync ruff format --check src/aeat/application/diagnostics.py src/aeat/application/test_diagnostics.py src/aeat/entrypoints/cli/_config.py src/aeat/entrypoints/cli/__init__.py src/aeat/entrypoints/cli/test_user_cli_surface.py`
- `uv run --no-sync ty check src/aeat/application/diagnostics.py src/aeat/entrypoints/cli/_config.py src/aeat/entrypoints/cli/__init__.py`
- `uv run --no-sync python -c "import yaml; [yaml.safe_load(open(p, encoding='utf-8')) for p in ['src/aeat/locales/es.yml','src/aeat/locales/en.yml','src/aeat/locales/ca.yml','src/aeat/locales/hu.yml']]; print('ok')"`
- `uv run --no-sync aeat config doctor`
- `uv run --no-sync aeat --format json config doctor`
- `uv run --no-sync aeat config doctor logs --lines 2`
- `uv run --no-sync aeat --help`

All verification commands passed.
