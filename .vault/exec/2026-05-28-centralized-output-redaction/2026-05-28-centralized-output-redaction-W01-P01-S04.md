---
tags:
  - '#exec'
  - '#centralized-output-redaction'
date: '2026-05-28'
modified: '2026-05-28'
step_id: 'S04'
related:
  - '[[2026-05-28-centralized-output-redaction-plan]]'
---

# `centralized-output-redaction` `W01.P01.S04`

Composed logging text scrubbing with the shared core redaction registry.

- Modified: `src/aeat/core/logging.py`
- Created: `.vault/exec/2026-05-28-centralized-output-redaction/2026-05-28-centralized-output-redaction-W01-P01-S04.md`

## Description

`SecretScrubbingFilter` now delegates shape-based log text redaction to `redact_for_log`, so NIF, URL path/query, and bearer-token matching come from `aeat.core.redaction`. Logging retains its transport-specific key-paired placeholder handling for cookies, passphrases, API keys, and certificate serial suffixes.

## Tests

- `uv run ruff check src/aeat/core/logging.py`
- `uv run pytest -q src/aeat/core/test_logging.py`
