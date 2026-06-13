---
tags:
  - '#exec'
  - '#centralized-output-redaction'
date: '2026-05-28'
modified: '2026-05-28'
step_id: 'S03'
related:
  - '[[2026-05-28-centralized-output-redaction-plan]]'
---

# `centralized-output-redaction` `W01.P01.S03`

Added core redaction canary tests for public CLI text and structured payloads.

- Created: `src/aeat/core/test_redaction.py`
- Created: `.vault/exec/2026-05-28-centralized-output-redaction/2026-05-28-centralized-output-redaction-W01-P01-S03.md`

## Description

The new tests exercise `redact_for_cli_output`, `redact_structured_for_cli_output`, and output classification policy resolution using real helper behavior. Canaries cover profile UUIDs, NIF values, bearer tokens, URL path/query stripping, object-key placeholders, nested structured payloads, tuple preservation, and the emit-only CLI output policy.

## Tests

- `uv run ruff check src/aeat/core/test_redaction.py src/aeat/core/redaction/__init__.py src/aeat/core/classification/__init__.py`
- `uv run pytest -q src/aeat/core/test_redaction.py`
