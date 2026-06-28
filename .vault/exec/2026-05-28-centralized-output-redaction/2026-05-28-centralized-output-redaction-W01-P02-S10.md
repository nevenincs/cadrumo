---
tags:
  - '#exec'
  - '#centralized-output-redaction'
date: '2026-05-28'
modified: '2026-05-28'
step_id: 'S10'
related:
  - '[[2026-05-28-centralized-output-redaction-plan]]'
---

# `centralized-output-redaction` `W01.P02.S10`

Routed JSON success-envelope emission through the central structured CLI redaction profile.

- Modified: `src/aeat/core/json_contract.py`
- Created: `.vault/exec/2026-05-28-centralized-output-redaction/2026-05-28-centralized-output-redaction-W01-P02-S10.md`

## Description

`emit_json_success` now builds the schema envelope payload and redacts it with `redact_structured_for_cli_output` before passing it to the generic JSON document writer. This enrolls successful JSON envelopes in the same profile, bucket, object-key, tax-id, URL, token, and sensitive-member-name redaction behavior used by the central command-output renderer while leaving `emit_json_document` available for lower-level generic JSON serialization.

## Tests

- `uv run ruff check src/aeat/core/json_contract.py src/aeat/core/test_json_envelope_roundtrip.py src/aeat/core/redaction/__init__.py src/aeat/core/test_redaction.py`
- `uv run pytest -q src/aeat/core/test_json_envelope_roundtrip.py src/aeat/core/test_output_rendering.py src/aeat/core/test_redaction.py`
