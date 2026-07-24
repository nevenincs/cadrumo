---
tags:
  - '#exec'
  - '#tui-wizard-substrate'
date: '2026-07-24'
modified: '2026-07-24'
step_id: 'S23'
related:
  - "[[2026-07-23-tui-wizard-substrate-plan]]"
---

# Prove resume re-validation, definition-change stale landing, loud no-op discard, and count-only diagnostics

## Scope

- `src/cadrumo/application/flows/tests/test_checkpoint_resume.py`

## Description

- Prove resume re-validation, definition-change stale landing, and the loud no-op discard against real persisted values.
- Assert diagnostics carry counts only, never persisted answer content.
- Landed in `10506c8833` (test_checkpoint_resume.py).

## Outcome

Resume behaviour is pinned with real-behavior tests: drifted answers land stale, unavailable-mode discard is loud, and the count-only diagnostic surface is proven to leak no answer values.

## Notes

None.
