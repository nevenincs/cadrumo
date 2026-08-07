---
tags:
  - '#exec'
  - '#unstructured-document-ingestion'
date: '2026-08-07'
modified: '2026-08-07'
body_schema: 'body-v1'
body_hash: 'sha256:e26949ec167dc95e4307c5b14f2392437d6064360791a62b3f4c224b6f1969e5'
step_id: 'S63'
related:
  - "[[2026-08-07-unstructured-document-ingestion-plan]]"
---
# Pace inference batch-wide: a standing contention refusal pauses the inference lane while every non-inference item completes

## Scope

- `src/cadrumo/application/ledger`

## Description

- Close the inference lane batch-wide on a standing contention refusal, leaving
  every document that reads without a model to run regardless.
- Add `paused` as the one status meaning the work did not happen, carrying no
  per-item refusal.
- State the cause once per run, with the provisioning snapshot's own causes and
  remediation.
- Separate deferral from failure, so a caller can tell "finished" from "the
  deterministic half is finished".

## Outcome

The lane closes two ways, and the asymmetry is the design rather than an
accident of implementation.

**Measured contention closes it BEFORE any attempt.** Admission control exists
precisely so an unsafe load is never attempted, so learning about it by
attempting would defeat the point.

**A missing reader closes it AFTER the first attempt.** Nothing is unsafe about
trying, there is no selected model for admission to judge, and predicting which
documents need a reader would mean reproducing the extractor's routing here — a
second copy of a decision that would drift from the first. One document pays for
the discovery and every later one is paused on it.

Classification is limited to the one question the shared shape probe already
answers: does this document carry a machine-readable record. Everything else is
treated as possibly needing a model. That is conservative in the safe direction —
the cost of over-pausing is a re-run that is free, and the cost of
under-pausing is the model load nobody admitted.

`paused` is deliberately not a failure and deliberately not silent. Nothing went
wrong with a paused document and a re-run costs nothing, but the run is not
finished either, so deferral is its own axis rather than folded into the failure
flag; one boolean cannot carry both claims.

The pause carries the provisioning snapshot's `causes`, `detail` and
`remediation` through verbatim. Flattening them would erase the distinction the
provisioning record was built around: reclaiming memory the local runtime holds
is an action this product can offer, and closing a peer application is not.

## Verification

    uv run --no-sync pytest src/cadrumo/application/ledger/tests/test_batch_ingest_runner.py src/cadrumo/application/ledger/tests/test_batch_ingest.py -m "unit or integration" -p no:randomly
    30 passed in 77.76s

Thirty collected, thirty ran, none deselected.

Five mutations from a plugin outside the repository, each reddening the property
it targets:

    ignore_contention             -> 5 failed, 13 passed
    pause_everything              -> 6 failed, 12 passed
    pause_without_saying_why      -> 2 failed, 16 passed
    deferred_counts_as_finished   -> 1 failed, 17 passed
    refuse_each_item_separately   -> 1 failed, 17 passed

### The mutation that caught a real defect

`refuse_each_item_separately` — never close the lane, so every affected document
collects its own copy of one identical environment refusal — **passed** against
the first implementation. That is the whole reason it was worth running.

The first version decided "this is the environment's fault, not the document's"
by matching the refusal's own remediation text against the provisioning verb.
That was wrong twice over. It coupled this module to strings another package
owns, and it silently HALF-worked: the text reader names a fixed provisioning
verb, while the vision reader composes its remediation from a runtime probe. So
one missing reader closed the lane for text-layer documents and left scans
refusing one by one — and the gate did not notice, because the test that
exercised the pause used the contention path, where the lane closes before any
attempt and the broken branch never runs.

The fix replaces the string match with a measurement: after a refusal, ask the
runtime once whether a reader is actually available. Same answer for both kinds
of document, no cross-package string coupling, and the mutation now reds.

### Two findings about the hardware seam, both measured rather than assumed

**Selection and admission share the free-memory bar.** A profile small enough to
refuse a load is also small enough that no model is selected, so it never
reaches the pacing decision. The reachable state where a model IS selected and
the load still refused is an accelerator whose free figure cannot be READ —
"could not tell" is not evidence of headroom, and refusing it is the primitive's
fail-closed core. Found by sweeping free-VRAM values and printing both answers,
after two guesses at the fixture were wrong.

**This host fails that check for real.** It reports no readable accelerator, so
its admission check refuses closed — correctly. Left to the host, every gate in
the file would have measured the pause path and none would have measured the
behaviour it names. The hardware profile is therefore injected in the tests,
through the same parameter the admission primitive exposes to its own suite, so
the production function computes every refusal from stated measurements rather
than having its decision substituted.

## Notes

No model was loaded, pulled, or contacted. The one test that needs a genuinely
absent reader points the runtime at a closed loopback port, so the client's
connect really fails rather than being told to.

That test also corrected its own expectation. It first asserted the remediation
was `aeat config provision pull`, per the brief. The real remediation is the
probe's own and said to start the runtime — which is *more* accurate, because in
that scenario the server is down rather than the model unprovisioned, and the
brief's fixed string would have sent the operator to download a model they may
already have. The assertion now pins the property.

The batch-wide cloud rate limiting the Step also names is **not built**. No
consented cloud route reaches this runner yet — the consent gate is still
unbuilt — so there is no dispatch here to apply a shared backoff across. Adding
one now would mean inventing the call site the consent design has not yet fixed,
which is the routing-around this campaign forbids. Recorded as an open remainder
of this Step rather than silently absorbed.
