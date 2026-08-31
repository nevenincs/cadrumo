---
tags:
  - '#exec'
  - '#tui-architecture'
date: '2026-08-28'
modified: '2026-08-28'
body_schema: 'body-v2'
body_hash: 'sha256:b53e89dc3ec2363aaa18125c502548b4f0e7576b3c6e52301dde18ca8f46d5d7'
step_id: 'S345'
related:
  - "[[2026-08-11-tui-architecture-plan]]"
---

# Bind the modal's response control ONCE per pending review instead of on every poll, which currently kills the operator's only way to answer after a single frame: the modal's interaction-state resolver calls the controller's response-control accessor on each poll, and the underlying response capability is SINGLE-USE. The first poll consumes it; every later availability check refuses with an unavailable-authority code, so the permitted-response set comes back empty and both the apply and reject controls are disabled -- permanently, at an unchanged revision, while the supervisor sits waiting for exactly the answer the interface can no longer send. Traced: the operation stays waiting-for-interaction at a fixed revision, controls live on one poll and dead on every poll after, unchanged for hundreds of cycles. THE CODE ALREADY DOCUMENTS THE CORRECT INVARIANT AND THE CALLER BREAKS IT -- the review-interaction type's own docstring states the control is bound exactly once per pending review because the capability is single-use, and that the same instance answers both the availability check and the eventual apply or reject. Operator consequence, which is the severity: a review modal offers its two controls for roughly one fifth of a second, then greys both out with no message and no recovery, since cancel depends on the definition and close refuses for a non-detachable operation. It fires for any operator who does not click within a single frame. Cache the bound control against the operation, pending interaction and revision, rebinding only when that triple changes. CRITICAL DETAIL FROM THE PROTOTYPE, so nobody ships the halfway version: the cached path must NOT re-run the availability check. The permitted intents were computed when the control was bound and remain valid while interaction and revision are unchanged, so a second check is one more consumption of the very capability being conserved -- a fix that caches the control but still inspects on every poll conserves nothing. Prove the controls remain live across MANY polls while the review is pending; a proof that samples once passes against the broken behaviour

## Scope

- `the modal interaction-state resolver`
- `the review-interaction binding and its cached availability`
- `and a multi-poll liveness proof of the response controls`

## Changes

- `M` `src/cadrumo/entrypoints/tui/operations/interactions.py`
- `M` `src/cadrumo/entrypoints/tui/operations/modal.py`
- `M` `src/cadrumo/entrypoints/tui/operations/tests/test_operation_modal_lifecycle.py`
- `verify:` `uv run --no-sync pytest src/cadrumo/entrypoints/tui/operations/tests -m integration -n0 -k "not detach_closes"` -> `pass`

## Notes

The interaction resolver bound a new response control on every poll, and the
capability behind it is single-use. The first bind consumed it, so every later
availability check returned an authority-unavailable refusal, the permitted
intent set was empty, and the operator's apply and reject controls went dead
after a single two-hundred-millisecond frame while the operation stayed in
waiting-for-interaction at an unchanged revision, still waiting for exactly
the answer the interface could no longer send. There was no recovery inside
the interface: cancellation depends on the definition and close refuses for a
non-detachable operation.

The review-interaction type's own docstring already declared the correct
invariant, that the control is bound exactly once per pending review because
the capability is single-use and the same instance answers both the
availability check and the eventual response. The one function that
constructed that type violated it on every poll. The resolver now takes the
state a repeating caller already holds and returns it unchanged while the same
interaction is pending at the same revision, so the modal owns the bound
control's lifetime and no second bind occurs.

This was reached from a flaky test rather than from reading the code. The
first hypothesis, shared by two readers, was that the wait was too short.
Instrumenting the message pump measured 49.7 milliseconds mean across 400
cycles, so the budget spanned 19.9 seconds of real time and the control was
still never enabled. Twenty seconds is not a race, and that single measurement
is what turned a flaky test into a product defect; the plausible fix would
have been a longer timeout, which would have buried a true failure
permanently.

Severity was under-called once and is corrected here. An earlier record
described this behaviour as fragile, reported rather than worked around, on
the strength of inference. With the trace in hand it is a dead end that fires
for any operator who does not answer within one frame, which is to say
essentially every operator.

The proof samples the controls across many consecutive polls rather than once,
because a single sample passes against the defect: the first frame was live
and only the frames after it were dead. Liveness is counted in the modal's own
poll intervals rather than in message-pump cycles, since a budget counted in
pumps can elapse without a single re-resolution having happened.

Gate proven by mutation: restoring the rebinding from outside the repository
reds the new proof, which names samples 1 through 23 as dead while sample 0
was live, and reds the apply case alongside it. Determinism was confirmed by a
controlled comparison rather than by repetition alone. Under the same
instrumented load the defect failed two runs out of two and the fix passed
three runs out of three, and the proof's own budget was not changed.

Discovery for this Step ran against the local fallback index rather than the
live semantic-search service, which was down.
