---
tags:
  - '#exec'
  - '#codebase-solidification'
date: '2026-05-30'
modified: '2026-05-30'
step_id: S464
related:
  - "[[2026-05-28-codebase-solidification-plan]]"
---

# `codebase-solidification` `W05.P26.S464`

Created `test_modelo_payloads.py` with 8 real-behaviour tests asserting `inputs_snapshot` roundtrips `dict[str, str]` through the CLI JSON channel and rejects non-string values.

- Created: `src/aeat/entrypoints/cli/test_modelo_payloads.py`

## Description

Tests cover all three payload classes (`CalculationRevisionPayload`, `WorkCalculateResult`, `WorkRevisionResult`):

- JSON roundtrip via `model_dump_json` / `model_validate_json` asserts strict pydantic equality.
- `ValidationError` is raised when an integer value is injected directly into the constructor.
- `ValidationError` is raised when a non-string value is injected via raw JSON deserialization.
- Anti-tautology proof: mutating one value in the serialized JSON blob produces strict model inequality, confirming the roundtrip boundary is not vacuous.

## Tests

8/8 passed. `uv run --no-sync pytest src/aeat/entrypoints/cli/test_modelo_payloads.py -v`. Commit `781f9c0fd`.
