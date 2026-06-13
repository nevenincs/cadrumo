---
tags:
  - '#exec'
  - '#centralized-output-redaction'
date: '2026-05-28'
modified: '2026-05-28'
step_id: 'S13'
related:
  - '[[2026-05-28-centralized-output-redaction-plan]]'
---

# `centralized-output-redaction` `W01.P02.S13`

Composed startup import-failure stderr with shared CLI redaction.

- Modified: `src/aeat/entrypoints/cli/__init__.py`
- Modified: `src/aeat/entrypoints/cli/test_workflow_surface.py`
- Modified: `src/aeat/locales/en.yml`
- Modified: `src/aeat/locales/es.yml`
- Modified: `src/aeat/locales/ca.yml`
- Modified: `src/aeat/locales/hu.yml`
- Created: `.vault/exec/2026-05-28-centralized-output-redaction/2026-05-28-centralized-output-redaction-W01-P02-S13.md`

## Description

Startup import-failure text now redacts the missing-dependency field before interpolation so sensitive module-name canaries cannot leak through the root callback failure surface. The startup locale string was also repaired through the canonical `aeat.locales` CLI to include the dependency and the `aeat config repair` recovery action, preserving the existing operator contract while enabling redacted dependency output.

## Tests

- `uv run ruff check src/aeat/entrypoints/cli/__init__.py src/aeat/entrypoints/cli/_errors.py src/aeat/entrypoints/cli/test_workflow_surface.py src/aeat/entrypoints/cli/test_windows_encoding.py`
- `uv run pytest -q src/aeat/entrypoints/cli/test_windows_encoding.py src/aeat/entrypoints/cli/test_workflow_surface.py -k "startup_import_failure or write_stderr or cp1252"`
- `uv run -q python -m aeat.locales audit`
