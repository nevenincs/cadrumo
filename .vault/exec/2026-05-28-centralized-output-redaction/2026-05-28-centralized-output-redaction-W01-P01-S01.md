---
tags:
  - '#exec'
  - '#centralized-output-redaction'
date: '2026-05-28'
modified: '2026-05-28'
step_id: 'S01'
related:
  - '[[2026-05-28-centralized-output-redaction-plan]]'
---

# `centralized-output-redaction` `W01.P01.S01`

Added the first centralized CLI public-output redaction profile primitives.

- Modified: `src/aeat/core/redaction/__init__.py`
- Created: `.vault/exec/2026-05-28-centralized-output-redaction/2026-05-28-centralized-output-redaction-W01-P01-S01.md`

## Description

The redaction module now defines exported placeholders for CLI public-output profile, bucket, and secure-object key values. It exposes `redact_for_cli_output` for rendered text and `redact_structured_for_cli_output` for JSON-shaped payloads.

The structured helper is key-aware: canonical profile, bucket, and secure-object key fields are converted to stable placeholders before serialization, while display labels pass through. Rendered text composes the existing AUDIT redaction rules with UUID, object-key assignment, and known secure-object token handling.

## Tests

- `uv run ruff check src/aeat/core/redaction/__init__.py`
- `uv run python -c "from aeat.core.redaction import redact_for_cli_output, redact_structured_for_cli_output; ..."`
