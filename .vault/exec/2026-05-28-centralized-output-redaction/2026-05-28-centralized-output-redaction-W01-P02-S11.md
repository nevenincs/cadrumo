---
tags:
  - '#exec'
  - '#centralized-output-redaction'
date: '2026-05-28'
modified: '2026-05-28'
step_id: 'S11'
related:
  - '[[2026-05-28-centralized-output-redaction-plan]]'
---

# `centralized-output-redaction` `W01.P02.S11`

Added JSON-envelope redaction roundtrip coverage for schema-preserving payloads.

- Modified: `src/aeat/core/test_json_envelope_roundtrip.py`
- Created: `.vault/exec/2026-05-28-centralized-output-redaction/2026-05-28-centralized-output-redaction-W01-P02-S11.md`

## Description

The JSON-envelope roundtrip suite now exercises `emit_json_success` with a strict output schema carrying sensitive profile, bucket, object-key, tax-id, URL, bearer-token, warning, and keyed-lookup canaries. The test asserts raw sensitive values are absent from rendered JSON, collision-safe redacted member names preserve entries, the outer envelope shape remains stable, and the redacted payload still validates through `SchemaEnvelope`.

## Tests

- `uv run ruff check src/aeat/core/json_contract.py src/aeat/core/test_json_envelope_roundtrip.py src/aeat/core/redaction/__init__.py src/aeat/core/test_redaction.py`
- `uv run pytest -q src/aeat/core/test_json_envelope_roundtrip.py src/aeat/core/test_output_rendering.py src/aeat/core/test_redaction.py`
