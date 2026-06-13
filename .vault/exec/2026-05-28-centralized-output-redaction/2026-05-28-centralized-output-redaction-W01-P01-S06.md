---
tags:
  - '#exec'
  - '#centralized-output-redaction'
date: '2026-05-28'
modified: '2026-05-28'
step_id: 'S06'
related:
  - '[[2026-05-28-centralized-output-redaction-plan]]'
---

# `centralized-output-redaction` `W01.P01.S06`

Migrated error-context value scrubbing to compose the shared log redaction rules.

- Modified: `src/aeat/core/errors/_registry.py`
- Created: `.vault/exec/2026-05-28-centralized-output-redaction/2026-05-28-centralized-output-redaction-W01-P01-S06.md`

## Description

`scrub_error_context` now keeps its existing key-based redaction for explicitly secret context keys, but non-secret context values are passed through `redact_for_log` after safe stringification. This brings error-envelope context values onto the same NIF, URL host-only, and bearer-token fingerprinting rules used by logs and the core redaction registry.

## Tests

- `uv run ruff check src/aeat/core/errors/_registry.py src/aeat/core/errors/test_envelope.py`
- `uv run pytest -q src/aeat/core/errors/test_envelope.py`
- `uv run pytest -q src/aeat/core/test_logging.py src/aeat/core/test_redaction.py src/aeat/core/errors/test_envelope.py`
