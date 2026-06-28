---
tags:
  - '#exec'
  - '#aeat-cli-hardening'
date: '2026-05-08'
modified: '2026-05-08'
related:
  - '[[2026-05-08-aeat-cli-hardening-plan]]'
  - '[[2026-05-08-aeat-cli-hardening-review-audit]]'
---



# `aeat-cli-hardening` `W7 Root Migration` `Version Surface`

Closed `A3` by adding the standard root version surfaces.

- Modified: `src/aeat/entrypoints/cli/__init__.py`
- Modified: `src/aeat/entrypoints/cli/test_user_cli_surface.py`
- Modified: `src/aeat/locales/es.yml`
- Modified: `src/aeat/locales/en.yml`
- Modified: `src/aeat/locales/ca.yml`
- Modified: `src/aeat/locales/hu.yml`
- Created: `src/aeat/application/diagnostics.py`
- Modified: `2026-05-08-aeat-cli-hardening-review.md`
- Created: `2026-05-08-aeat-cli-hardening-W7-version-surface.md`

## Description

The root CLI now supports `aeat --version`, `aeat -V`, and `aeat version`.
The `version` command also supports the existing root JSON format flag.

Registry counts are built by a typed application report in the diagnostics
module. The command handler renders that report and does not own registry
loading or counting logic.

The first attempt failed for root flags because Typer did not call the callback
when no command was present. The root app now invokes the callback without a
command so eager version flags are honored while plain `aeat` still renders
help.

## Tests

Verification commands:

- `uv run --no-sync aeat --version`
- `uv run --no-sync aeat -V`
- `uv run --no-sync aeat version`
- `uv run --no-sync aeat --format json version`
- `uv run --no-sync aeat`
- `uv run --no-sync aeat --help`
- `uv run --no-sync pytest src/aeat/entrypoints/cli/test_user_cli_surface.py -k "version or root_surface"`
- `uv run --no-sync ruff check src/aeat/application/diagnostics.py src/aeat/entrypoints/cli/__init__.py src/aeat/entrypoints/cli/test_user_cli_surface.py`
- `uv run --no-sync ruff format --check src/aeat/application/diagnostics.py src/aeat/entrypoints/cli/__init__.py src/aeat/entrypoints/cli/test_user_cli_surface.py`
- `uv run --no-sync ty check src/aeat/application/diagnostics.py src/aeat/entrypoints/cli/__init__.py`
- `uv run --no-sync python -c "import yaml, pathlib; [yaml.safe_load(pathlib.Path(p).read_text(encoding='utf-8')) for p in ['src/aeat/locales/es.yml','src/aeat/locales/en.yml','src/aeat/locales/ca.yml','src/aeat/locales/hu.yml']]; print('locale yaml ok')"`

The initial `--version` and `-V` direct checks failed before the
`invoke_without_command` repair. The final verification commands passed.
