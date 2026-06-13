---
tags:
  - '#exec'
  - '#centralized-output-redaction'
date: '2026-05-28'
modified: '2026-05-28'
step_id: 'S14'
related:
  - '[[2026-05-28-centralized-output-redaction-plan]]'
---

# `centralized-output-redaction` `W01.P02.S14`

Composed the CLI error-boundary stderr writer with shared redaction.

- Modified: `src/aeat/entrypoints/cli/_errors.py`
- Modified: `src/aeat/entrypoints/cli/test_windows_encoding.py`
- Modified: `src/aeat/locales/en.yml`
- Modified: `src/aeat/locales/es.yml`
- Modified: `src/aeat/locales/ca.yml`
- Modified: `src/aeat/locales/hu.yml`
- Created: `.vault/exec/2026-05-28-centralized-output-redaction/2026-05-28-centralized-output-redaction-W01-P02-S14.md`

## Description

`write_stderr` now passes every stderr payload through `redact_for_cli_output` before writing to the configured stream or fallback byte buffer. This preserves the existing UTF-8-safe fallback behavior while adding a final redaction boundary for text and JSON error payloads. Locale audit also identified a missing live-IVA timeout message key, which was filled through `aeat.locales` so the localization gate is green for this stderr work.

## Tests

- `uv run ruff check src/aeat/entrypoints/cli/__init__.py src/aeat/entrypoints/cli/_errors.py src/aeat/entrypoints/cli/test_workflow_surface.py src/aeat/entrypoints/cli/test_windows_encoding.py`
- `uv run pytest -q src/aeat/entrypoints/cli/test_windows_encoding.py src/aeat/entrypoints/cli/test_workflow_surface.py -k "startup_import_failure or write_stderr or cp1252"`
- `uv run -q python -m aeat.locales audit`
