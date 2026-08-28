---
tags:
  - '#exec'
  - '#tui-architecture'
date: '2026-08-28'
modified: '2026-08-28'
body_schema: 'body-v2'
body_hash: 'sha256:7b5f45b0de6107933dc8b9cb5b20f10702a9f8290b91c56593e94c99c59de474'
step_id: 'S99'
related:
  - "[[2026-08-11-tui-architecture-plan]]"
---

# Prove modal detach, close refusal, apply, reject, and cancel behavior never assumes process ownership

## Scope

- `src/cadrumo/entrypoints/tui/operations/tests/test_operation_modal_lifecycle.py`

## Changes

- `M` `src/cadrumo/entrypoints/tui/operations/tests/test_operation_modal_lifecycle.py`
- `verify:` `uv run --no-sync pytest src/cadrumo/entrypoints/tui/operations/tests/test_operation_modal_lifecycle.py -m integration -n0 -k "not detach"` -> `pass`

## Notes

Four of the row's five behaviours are proven: close refusal against the
registered request-cancel close policy, cooperative cancellation, apply, and
reject, each driven through the installed modal against real supervised
operations.

Detach is carried forward, not claimed and not abandoned. Its behaviour is
proven correct up to modal teardown: the detach control is enabled, the click
returns the detached outcome carrying the right operation identity and
revision, and a controller-level probe settles the same detach on a running
operation in milliseconds. Modal teardown after that dismissal does not
return, because the journal's observation read acquires a synchronous OS file
lock on the event loop and the modal's polling worker cannot be cancelled
inside it. That is a production defect tracked separately; the deselected case
remains in the file so it reds when the defect is repaired incorrectly.

Gate proven by mutation: dismissing on close unconditionally, neutering the
cancel request, and routing reject through apply each red the suite, applied
as runtime patches from outside the repository.

Discovery for this Step ran against the local fallback index rather than the
live semantic-search service, which was down.
