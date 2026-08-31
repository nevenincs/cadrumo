---
tags:
  - '#exec'
  - '#tui-interface'
date: '2026-08-31'
modified: '2026-08-31'
body_schema: 'body-v2'
body_hash: 'sha256:c293db6a3d62e9bb93543938913cf75eea4a97d2b68a241703128cf291ca5670'
step_id: 'S75'
related:
  - "[[2026-08-11-tui-interface-plan]]"
---

# Build the mandatory modelo.edit.review transaction gate with every changed semantic address, scalar and row intent, addressable validation, focus return, unsaved-change stay or abandon choice, and no fabricated supervisor approval

## Scope

- `src/cadrumo/entrypoints/tui/modelo/edit/review.py`

## Changes

- `A` `src/cadrumo/entrypoints/tui/modelo/edit/review.py`
- `M` `src/cadrumo/entrypoints/tui/modelo/edit/tests/test_rows_and_review.py`
- `verify:` `pytest entrypoints/tui/modelo/edit` -> `17 passed`

## Notes

NO FABRICATED SUPERVISOR APPROVAL, which is the row's sharpest requirement. The
gate returns the contract's own preflight verdict UNMODIFIED and never says
'approved'. A green preflight is review material, not authorization: the
execution path independently repeats every concurrency and capability check at
the guarded commit point, and a surface reporting approval would be inventing a
decision it has no standing to make. The summary carries the preflight through
rather than re-shaping it, because a surface-local summary of a contract
verdict is a second reading of the same facts, free to disagree with the first.

TWO KINDS OF BLOCKER, kept apart because they are resolved differently.
SURFACE blockers are unresolved lexemes: nothing is staged for them, so
submitting would file the value the field held BEFORE the operator typed over
it while the screen shows the new text. CONTRACT findings come from preflight
and describe the staged submission itself. The gate refuses on surface blockers
BEFORE calling preflight, so a real recheck is not spent on a request the
operator did not mean.

A refusal NAMES the controls to return to. That is what makes it actionable:
a gate reporting errors without saying where sends the operator searching.

AN EMPTY EDIT IS NOT REVIEWABLE. Offering review over nothing invites
confirming a submission with no intents, which either does nothing or looks
like it did something, and neither is honest.

LEAVING OFFERS EXACTLY TWO ANSWERS -- stay or abandon. A silent save on
navigation is deliberately absent: an edit the operator did not review is an
edit they did not approve, and filing one would be a declaration nobody
confirmed.
