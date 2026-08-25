---
tags:
  - '#exec'
  - '#tui-architecture'
date: '2026-08-25'
modified: '2026-08-25'
body_schema: 'body-v1'
body_hash: 'sha256:68471b1bd8d1765949f4c594c0369ecfb4ae3aec5eb13c87f85540b91e5a92e0'
step_id: 'S50'
related:
  - "[[2026-08-11-tui-architecture-plan]]"
---
# Relocate generic dialogs while keeping approval and operation lifecycle out of component state

## Scope

- `src/cadrumo/entrypoints/tui/components/dialogs.py`
- `src/cadrumo/entrypoints/tui/components/tests/test_dialogs.py`
- direct form-dialog consumer and legacy facade cleanup

## Description

- Move `TextEditScreen`, `ChoiceEditScreen`, and `OneChoiceEditScreen` into the canonical dialogs component module.
- Move local dialog styling and presentation-only state with the dialogs, while leaving form-page routing in the inbound adapter.
- Remove the legacy adapter facade exports and add direct Textual pilot coverage at the canonical component boundary.

## Outcome

The three generic edit dialogs have one canonical owner. The components facade remains inert, and the dialogs retain no approval, operation, or sensitive-recovery lifecycle state.

Independent review approved commit `66f2f0387d` on 2026-08-25.

## Notes

Verification evidence:

- Focused sequential Textual tests passed: 13 tests in `components/tests/test_dialogs.py` and `adapters/inbound/tui/tests/test_form_screen.py`.
- Ruff check and formatting check passed for all four relocated or consumer files.
- `ty check` passed for the relocated production and consumer modules.
- Full `pytest --collect-only -q` completed: 27,448 collected and 4,298 deselected in 77.03 seconds, with one existing collection warning.

The optional shared-tree import-hygiene and test-inventory gates reported unrelated concurrent work outside this Step's scoped paths; no S50 gate failure remained.
