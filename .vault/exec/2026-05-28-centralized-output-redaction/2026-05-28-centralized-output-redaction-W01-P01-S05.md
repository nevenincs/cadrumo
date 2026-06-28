---
tags:
  - '#exec'
  - '#centralized-output-redaction'
date: '2026-05-28'
modified: '2026-05-28'
step_id: 'S05'
related:
  - '[[2026-05-28-centralized-output-redaction-plan]]'
---

# `centralized-output-redaction` `W01.P01.S05`

Added logging regression coverage for shared redaction behavior and fixed the discovered scrub order defect.

- Modified: `src/aeat/core/test_logging.py`
- Modified: `src/aeat/core/logging.py`
- Created: `.vault/exec/2026-05-28-centralized-output-redaction/2026-05-28-centralized-output-redaction-W01-P01-S05.md`

## Description

The new logging canary proves NIF, URL path/query, and bearer-token shaped arguments are redacted through the logging pipeline without relying on local sensitive-key hints. The test exposed that local `token=` assignment scrubbing could run inside URL queries before host-only URL redaction, producing malformed `https://host<redacted>` output. `_scrub_text` now applies shared `redact_for_log` first, then applies logging-specific assignment and provider-key fallback redaction.

## Tests

- `uv run ruff check src/aeat/core/logging.py src/aeat/core/test_logging.py`
- `uv run pytest -q src/aeat/core/test_logging.py`
