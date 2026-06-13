---
step_id: S36
tags:
  - '#exec'
  - '#codebase-solidification'
date: '2026-05-28'
modified: '2026-05-28'
related:
  - '[[2026-05-28-codebase-solidification-plan]]'
  - '[[2026-05-27-centralized-module-drift-audit]]'
---

# codebase-solidification W01.P01.S36 — TestUnhandledEnvelope real-behavior tests

## Outcome

Added class `TestUnhandledEnvelope` to
`src/aeat/application/workflow/test_engine.py` with 12 tests covering:

- `test_envelope_code_for_value_error` — direct envelope assertion
- `test_envelope_code_for_type_error` — direct envelope assertion
- `test_envelope_code_for_key_error` — direct envelope assertion
- `test_envelope_code_for_runtime_error` — direct envelope assertion
- `test_envelope_code_for_attribute_error` — direct envelope assertion
- `test_envelope_context_carries_stage_and_error_type` — context field assertions
- `test_computing_deadlines_unhandled_emits_envelope_code` — real engine path via `_ConcreteDeadlineEngine.raise_exc = ValueError`
- `test_checking_inbox_unhandled_emits_envelope_code` — via `_ConcreteNotificationsSource.raise_exc = TypeError`
- `test_building_draft_expedientes_unhandled_emits_envelope_code` — via `_ConcreteExpedientesSource.raise_exc = KeyError`
- `test_building_draft_inputs_unhandled_emits_envelope_code` — via `_ConcreteInputsProvider.raise_exc = RuntimeError`
- `test_building_draft_builder_unhandled_emits_envelope_code` — via `_ConcreteDraftBuilder.raise_exc = AttributeError`
- `test_running_preflight_unhandled_emits_envelope_code` — via `_ConcreteSubmissionEngine.preflight_exc = OSError`

Added `raise_exc: BaseException | None = None` field to
`_ConcreteExpedientesSource` and `_ConcreteNotificationsSource` to enable
the new catch-site trigger paths. Added imports:
`build_error_envelope`, `ErrorCategory`, `UnhandledWorkflowError`.

No mocks, no skips, no tautological assertions — all tests exercise real
engine execution paths and assert `code == "INTERNAL_WORKFLOW_UNHANDLED"`.

## Files touched

- `src/aeat/application/workflow/test_engine.py` — `TestUnhandledEnvelope` class + seam field additions

## Verification

`uv run --no-sync pytest src/aeat/application/workflow/test_engine.py -x`: 46 passed

## Commit

`8fd526d02`
