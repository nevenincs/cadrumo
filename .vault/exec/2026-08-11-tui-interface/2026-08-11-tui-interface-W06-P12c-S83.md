---
tags:
  - '#exec'
  - '#tui-interface'
date: '2026-08-31'
modified: '2026-08-31'
body_schema: 'body-v2'
body_hash: 'sha256:e0b069983be7f21a891b73deb7318174433c18d0c4f329e8036ddc15ea5a4f7a'
step_id: 'S83'
related:
  - "[[2026-08-11-tui-interface-plan]]"
  - "[[2026-08-11-tui-interface-W06-P12c-S82]]"
---

# Enroll discard only through its canonical destructive lifecycle capability, exact approval interaction, and registered operation, and prove refusal, cancellation, effect, refresh, focus return, and every supported geometry independently

## Scope

- `src/cadrumo/entrypoints/tui/modelo/tests/test_c4_discard_action.py`

## Changes

- `A` `src/cadrumo/entrypoints/tui/modelo/action/discard.py`
- `A` `src/cadrumo/entrypoints/tui/modelo/tests/test_c4_discard_action.py`
- `verify:` `pytest test_c4_discard_action.py test_c4_rename_action.py` -> `18 passed`

## Notes

THE EXACT-APPROVAL INTERACTION IS THE BASELINE, and the enrolment's design
turns on refusing to fill it locally. The registered operation declares
`OperationBaselinePolicy.EXACT_APPROVAL`, and the request carries a
`ModeloWorkDiscardBaseline` holding the unit's name and `observed_updated_at`
AS THE OPERATOR SAW THEM. Those arrive as REQUIRED parameters with no defaults,
asserted on the signature, because a function that resolved them for itself
would produce a baseline matching the tree by construction: the platform's
compare-and-swap would always pass, and the operator would be recorded as
approving a state they never saw. A second proof shows two approvals of
different observed states are distinguishable -- without that, staleness has
nothing to compare.

CANCELLATION IS PROVEN BY ITS ABSENCE. The operation declares
`OperationCancellation.UNSUPPORTED`, so the surface must not offer to cancel a
discard. On a destructive action specifically, an affordance that cannot work
is worse than no affordance: an operator who believes they cancelled, and did
not, learns otherwise only from the absence of the thing they meant to keep.
Both the cancellation and baseline policies are READ from the definition rather
than restated, so a change to either surfaces here, where the baseline is
built.

A GATE OF MINE THAT WAS WRONG ABOUT ITS SUBJECT, caught by itself. The
cancellation proof first searched the module source for the word "cancel" and
fired -- on this module's own docstring EXPLAINING that cancellation is
unsupported. It forbade documenting the constraint rather than offering the
affordance. This is the same defect class as the `_workspace_producers`
substring scan repaired under W05.P10a.S49 earlier in this session, and the
same one W07.P16.S340 warns against in its note refusing a name-matching gate:
match the STRUCTURE, not the spelling. It now walks the AST for a call whose
func mentions cancellation, so prose is free and a request is refused.

A blank discard reason is refused while an absent one is accepted, because
recording no reason and recording an empty reason are different claims -- an
empty string reads later as a reason that was given and lost.

As with rename, the action reaches the registered operation and never
`work_lifecycle`, asserted against the module's AST, and submits without
starting so a destructive run cannot execute with no window observing it.
