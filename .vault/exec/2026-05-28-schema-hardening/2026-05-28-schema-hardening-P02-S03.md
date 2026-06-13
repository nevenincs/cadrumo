---
tags:
  - '#exec'
  - '#schema-hardening'
date: '2026-06-02'
modified: '2026-06-02'
step_id: 'S03'
related:
  - "[[2026-05-28-schema-hardening-continuity-conformance-plan]]"
---




# Add real-behavior tests for retired repurposed and unmatched continuity decisions

## Scope

- `src/aeat/domain/calculations/registry/test_cross_revision_drift.py`

## Description

Audited current state of
`src/aeat/domain/calculations/registry/test_cross_revision_drift.py`
against the P02.S03 brief.

## Outcome

Already implemented. The test file (751 lines) already carries the
four real-behavior tests for the retired / unmatched-continuity
validator semantics:

- `test_strict_continuity_validation_requires_retired_decision_for_missing_surface`
- `test_strict_continuity_validation_accepts_retired_decision_for_missing_surface`
- `test_strict_continuity_validation_rejects_unmatched_evolution_continuity_id`
- `test_strict_continuity_validation_rejects_retired_decision_when_target_surface_remains`

Each builds a ModeloDefinition through the loader, exercises the
validator entry point, and asserts the typed refusal or accepted
path. No mocks; real adapters. The P02.S06 evidence record
(commit `76dc28fe8`) already captured the broader run: 92 pass / 1
fail (the failure is a peer-corpus-growth pre-existing issue in
test_loader_directory_mode.py, not authored by P02).

## Notes

Like P02.S02, this Step's implementation predates the carve-out;
closure is structural documentation. The 92-pass figure includes
these four S03 tests.
