---
tags:
  - '#exec'
  - '#centralized-output-redaction'
date: '2026-05-28'
modified: '2026-05-28'
step_id: 'S08'
related:
  - '[[2026-05-28-centralized-output-redaction-plan]]'
---

# `centralized-output-redaction` `W01.P02.S08`

Enrolled the central command-output renderer in CLI success-output redaction for text and JSON.

- Modified: `src/aeat/core/redaction/__init__.py`
- Modified: `src/aeat/core/output_rendering.py`
- Created: `.vault/exec/2026-05-28-centralized-output-redaction/2026-05-28-centralized-output-redaction-W01-P02-S08.md`

## Description

`render_command_output` now redacts JSON-shaped payloads after project-type normalization and before serialization, preserving the emitted structure while replacing sensitive profile, bucket, object-key, tax-id, URL, and token values through the shared CLI output redaction profile. Text output lines are redacted at the same rendering boundary before they are joined for emission. Review found that string mapping keys could carry sensitive identifiers, so the central structured CLI redaction helper now redacts dictionary member names as well as values while retaining the original keys for value-classification decisions.

## Tests

- `uv run ruff check src/aeat/core/redaction/__init__.py src/aeat/core/test_redaction.py src/aeat/core/output_rendering.py src/aeat/core/test_output_rendering.py`
- `uv run pytest -q src/aeat/core/test_output_rendering.py src/aeat/core/test_redaction.py`
