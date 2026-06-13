---
tags:
  - '#exec'
  - '#secure-storage-production-hardening'
date: '2026-05-27'
modified: '2026-05-27'
step_id: 'S403'
related:
  - '[[2026-05-22-secure-storage-production-hardening-refactor-plan]]'
---

# `secure-storage-production-hardening` `W15.P30.S403`

Reproduced the Modelo work-create validation refusal and isolated it to strict CLI output-schema validation, not to encrypted bucket persistence or profile enrollment.

- Modified: none
- Created: this step record

## Description

The failing surface was reproduced with the real CLI path in `test_modelo_casilla_normalisation.py`, where `aeat app modelo work create --format json` returned `REFUSED_CLI_VALIDATION_BOUNDARY` before the test could calculate a work unit.

Inspection showed the command had created or loaded the work-unit lane far enough to build the response, then failed while validating `WorkCreateResult`. The create command supplies `name_applied=None` for fresh creates and idempotent reuses without a rename, while the strict schema required `name_applied: str`.

That mismatch caused a pydantic `ValidationError` inside the Typer callback. The shared CLI boundary correctly caught it, but the operator-facing result was a generic validation-boundary refusal, masking the real contract drift.

## Tests

Initial reproduction:

- `uv run pytest -q src/aeat/entrypoints/cli/test_modelo_casilla_normalisation.py::test_bare_numeric_unknown_casilla_surfaces_helpful_message`

Observed blocker:

- `REFUSED_CLI_VALIDATION_BOUNDARY` emitted by `modelo work create`
- no evidence that the isolated encrypted bucket database failed to open
