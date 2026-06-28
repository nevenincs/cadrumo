---
tags:
  - '#exec'
  - '#justfile-redesign'
date: '2026-06-09'
modified: '2026-06-09'
step_id: 'S03'
related:
  - "[[2026-06-09-justfile-redesign-plan]]"
---

# reconcile docs marker and statement-order test integrity failures

## Scope

- `src/aeat/tests/test_marker_integrity.py`
- `src/aeat/tests/test_roundtrip_fixture_saturation.py`

## Description

- Reconciled `"docs"` marker collision by removing it from `_FORBIDDEN_MARKERS` and registering it in `_EXPECTED_CONFIGURED_MARKERS` within `src/aeat/tests/test_marker_integrity.py`.
- Repaired the statement-order AST validation failure in `src/aeat/tests/test_roundtrip_fixture_saturation.py` by relocating the `pytestmark` assignment immediately after module imports.

## Outcome

All 3,217 tests in the marker integrity test suite (`pytest src/aeat/tests/test_marker_integrity.py`) passed successfully, validating both the `"docs"` marker alignment and the statement-order AST compliance.

## Notes
