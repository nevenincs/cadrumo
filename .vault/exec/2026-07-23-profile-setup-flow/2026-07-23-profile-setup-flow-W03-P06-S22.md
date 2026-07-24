---
tags:
  - '#exec'
  - '#profile-setup-flow'
date: '2026-07-24'
modified: '2026-07-24'
step_id: 'S22'
related:
  - "[[2026-07-23-profile-setup-flow-plan]]"
---

# Surface modify-mode save-and-exit unavailability with an explicit message and a loud staged-edit discard on interruption

## Scope

- `src/cadrumo/application/wizard/_commands.py`

## Description

The modify-mode honesty-surfacing half of the `34c27ab287` landing
(one cohesive change with S21; full detail in the S21 record):
save-and-exit unavailability rendered at the real save attempt, the
staged-only disclosure notice on every interactive modify envelope, and
the declaration test pinning `checkpoint_available(MODIFY) is False`.

## Outcome

Verified with the S21 half: honesty suite 5/5 within the 13/13 landing
run; both operator moments asserted on rendered surfaces through real
frontend paths, never on key existence alone.

## Notes

Gate run performed as one landing with S21 because the projection and
the honesty notices share the interactive-edit preparation seam.

