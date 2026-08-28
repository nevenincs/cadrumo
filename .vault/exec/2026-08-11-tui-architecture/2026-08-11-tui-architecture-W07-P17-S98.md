---
tags:
  - '#exec'
  - '#tui-architecture'
date: '2026-08-28'
modified: '2026-08-28'
body_schema: 'body-v2'
body_hash: 'sha256:4bcc43d0420964f60eae708d40c8e1390600bffbc7a235c12347ced29a858dd1'
step_id: 'S98'
related:
  - "[[2026-08-11-tui-architecture-plan]]"
---


# Prove spinner, phase, deadline, cancellation availability, live logs, diagnostic detail, review content, and terminal receipts follow supervisor revisions

## Scope

- `src/cadrumo/entrypoints/tui/operations/tests/test_operation_modal.py`

## Changes

- `M` `src/cadrumo/entrypoints/tui/operations/tests/test_operation_modal.py`
- `verify:` `uv run --no-sync pytest src/cadrumo/entrypoints/tui/operations/tests -m integration -n0 -k "not detach_closes"` -> `pass`

## Notes

All eight facts the row names are proven against a real supervised operation
driven through the installed modal: spinner and terminal copy, phase,
deadlines, cancellation availability, live logs, review content, diagnostic
detail and terminal receipts.

The REVIEW is answered by pressing the modal's own apply control rather than
from outside. It cannot be answered from outside while the modal watches: the
response capability is single-use and the modal's poll loop has already bound
it, so an out-of-band bind is refused. Answering before the modal mounts
settles the operation first and leaves nothing to observe, which is the
difference between watching a lifecycle and watching one already finished.

Rendered state is proven to follow supervisor revisions: every sampled frame
carries the revision it was drawn from, the sequence never regresses, and an
anti-vacuity assertion requires more than one distinct revision so a modal
that rendered once cannot pass.

The terminal receipt is proven to reach its widget through a separate route.
It cannot be read off a widget during the settling frame, because the modal
draws that frame and dismisses within a single pause and the widget tree is
gone when control returns. So a real operation is driven to settlement, its
settled projection is turned into a view model by the production derivation,
and that view model is handed to the modal's own render method on a mounted
screen. Data and renderer are both production; only the moment is chosen.

Diagnostic detail is proven in its absent direction: this operation succeeds,
so the projection carries no diagnostic and the row is asserted blank on every
frame rather than holding a value it was never given.

Gate proven by mutation, applied as runtime patches from outside the
repository: suppressing the detail render reds three tests, freezing the view
model so the modal stops following the supervisor reds two, and corrupting the
settled-receipt derivation reds the divergence proof.

One observation recorded rather than acted on: the modal rebinds the
single-use response capability on every poll, so the apply affordance is
reliably offered only on the first poll after a REVIEW appears. It did not
block this Step, and a test that drove the control promptly always found it,
but it is fragile and is reported rather than worked around.

Discovery for this Step ran against the local fallback index rather than the
live semantic-search service, which was down.
