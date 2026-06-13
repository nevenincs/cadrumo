---
tags:
  - '#exec'
  - '#centralized-output-redaction'
date: '2026-05-28'
modified: '2026-05-28'
step_id: 'S09'
related:
  - '[[2026-05-28-centralized-output-redaction-plan]]'
---

# `centralized-output-redaction` `W01.P02.S09`

Added renderer-level redaction canaries for text and JSON output.

- Modified: `src/aeat/core/test_redaction.py`
- Modified: `src/aeat/core/test_output_rendering.py`
- Created: `.vault/exec/2026-05-28-centralized-output-redaction/2026-05-28-centralized-output-redaction-W01-P02-S09.md`

## Description

The output-rendering tests now exercise the public `render_command_output` API with real sensitive canaries in text lines and nested JSON payloads. Coverage asserts raw profile ids, tax ids, bearer tokens, URLs, and secure-object keys do not reach rendered output, including when those canaries appear as JSON object member names. Normal project types such as `Path`, `Decimal`, and `date` remain serialized in the existing JSON shape. Core redaction helper coverage also now asserts sensitive dictionary keys are redacted before rendering.

## Tests

- `uv run ruff check src/aeat/core/redaction/__init__.py src/aeat/core/test_redaction.py src/aeat/core/output_rendering.py src/aeat/core/test_output_rendering.py`
- `uv run pytest -q src/aeat/core/test_output_rendering.py src/aeat/core/test_redaction.py`
