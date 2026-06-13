---
tags:
  - '#exec'
  - '#centralized-output-redaction'
date: '2026-05-28'
modified: '2026-05-28'
step_id: 'S07'
related:
  - '[[2026-05-28-centralized-output-redaction-plan]]'
---

# `centralized-output-redaction` `W01.P01.S07`

Updated error-envelope redaction tests for shared rule behavior.

- Modified: `src/aeat/core/errors/test_envelope.py`
- Created: `.vault/exec/2026-05-28-centralized-output-redaction/2026-05-28-centralized-output-redaction-W01-P01-S07.md`

## Description

The envelope privacy test now asserts that context tax identifiers, URL paths/queries, and bearer tokens are redacted through both JSON and text rendering. The obsolete expectation that `profile_tax_id` remains raw in the JSON envelope was removed.

## Tests

- `uv run ruff check src/aeat/core/errors/_registry.py src/aeat/core/errors/test_envelope.py`
- `uv run pytest -q src/aeat/core/errors/test_envelope.py`
- `uv run pytest -q src/aeat/core/test_logging.py src/aeat/core/test_redaction.py src/aeat/core/errors/test_envelope.py`
