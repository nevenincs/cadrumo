---
tags:
  - '#exec'
  - '#centralized-output-redaction'
date: '2026-05-28'
modified: '2026-05-28'
step_id: 'S12'
related:
  - '[[2026-05-28-centralized-output-redaction-plan]]'
---

# `centralized-output-redaction` `W01.P02.S12`

Routed `_emit_envelope` text emission through the central redacted renderer.

- Modified: `src/aeat/entrypoints/cli/_common.py`
- Created: `src/aeat/entrypoints/cli/test_common_output.py`
- Created: `.vault/exec/2026-05-28-centralized-output-redaction/2026-05-28-centralized-output-redaction-W01-P02-S12.md`

## Description

`_emit` was already enrolled in `render_command_output`. `_emit_envelope` now uses that renderer for text-mode lines instead of joining and echoing them directly, while JSON mode continues through the redacted `emit_json_success` path. The new test exercises `_emit_envelope` with a real Click context and captured stdout to prove text-mode envelope lines redact profile identifiers at the transport boundary.

## Tests

- `uv run ruff check src/aeat/entrypoints/cli/_common.py src/aeat/entrypoints/cli/test_common_output.py src/aeat/core/output_rendering.py src/aeat/core/test_output_rendering.py`
- `uv run pytest -q src/aeat/entrypoints/cli/test_common_output.py src/aeat/core/test_output_rendering.py src/aeat/core/test_json_envelope_roundtrip.py`
