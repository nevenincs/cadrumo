---
tags:
  - '#exec'
  - '#unstructured-document-ingestion'
date: '2026-08-07'
modified: '2026-08-08'
body_schema: 'body-v1'
body_hash: 'sha256:3c51ed8afdc7eb59d203cd8c8fe232f64008869b4ea03caadc08b218979eba4a'
step_id: 'S63'
related:
  - "[[2026-08-07-unstructured-document-ingestion-plan]]"
---
# Pace inference batch-wide: a standing contention refusal pauses the inference lane while every non-inference item completes

## Scope

- `src/cadrumo/application/ledger`

## Description

- Add a process-wide, per-provider rate-limit window armed when a dispatch is rate limited and awaited before any later dispatch at that provider.
- Arm the window before the retry loop decides whether the current request may continue, so a limit found on the final attempt still paces the run.
- Bound the shared wait by the retry budget, leaving the window armed and readable rather than blocking on it.
- Carry a per-item record of whether a document needed the inference lane, and report deterministic-completed and paced as separate run figures.
- Extend the batch CLI payload with both figures and the per-item flag.

## Outcome

A rate limit now paces the run rather than the request that met it. Per-item backoff against a shared limit is not a rate limit: N items each discover the same account-wide window independently and issue N calls into it, which is N limits being ignored rather than one being respected.

The batch's pausing half was already in place -- deterministic items keep completing while inference-bearing ones park, with one run-level cause rather than N identical refusals stamped onto innocent documents. What was missing was the ability to SEE it. A completed row looks identical whether it was read by a parser or through a model, so a pooled figure reports a run that paced everything and a run that paced nothing the same way. The two counts are now separate, and the completed set is derived by subtraction from the status taxonomy so a new success-shaped status counts as progress by construction rather than being silently omitted.

## Verification

uv run --no-sync pytest src/cadrumo/llm/tests/test_shared_rate_limit_pacing.py -m unit -p no:randomly -n 0 -q
    5 passed in 6.71s

    uv run --no-sync pytest src/cadrumo/application/ledger/tests/test_batch_ingest.py src/cadrumo/application/ledger/tests/test_batch_ingest_runner.py src/cadrumo/application/ledger/tests/test_batch_inference_pacing.py -m integration -p no:randomly -n 0 -q
    24 passed, 12 deselected in 113.23s (0:01:53)

    uv run --no-sync pytest src/cadrumo/entrypoints/cli/tests/test_json_schema_conformance.py -m "unit or integration" -p no:randomly -n 0 -q
    333 passed in 40.19s

The pacing is measured at the SERVER, on the gap between arrivals, because that is where the question is decided: a client that recorded a delay and dispatched anyway would look identical from inside. The control runs the same two dispatches without the rate limit and asserts the gap is small, which establishes both that the measured gap is the pacing rather than fixture overhead and that a paced dispatch genuinely would have gone immediately.

The batch control runs the same folder with headroom available and asserts nothing paced, which is what makes the parked row a window that OPENED rather than an item that could never have been read either way.

Proven by two mutations. Removing the shared wait turned the two cross-item pacing cases red while the controls stayed green; making a closed lane park every item turned the deterministic-progress case red while the two headroom controls, where the lane never closes, stayed green.

## Notes

The contended batch case needed a widened safety margin to be reachable at all. On the shipped catalogue, selection and admission read the same measured free figure and their thresholds sit within tens of megabytes of each other, so a headroom low enough to refuse admission is usually also low enough for selection to find no candidate -- which is deliberately NOT a pause. The first attempt at this fixture fell into exactly that gap and reported a paced count of zero while the run had actually closed its lane for a different reason. The margin is a real operator setting, raised on a machine that also drives a display, so widening it separates the two thresholds without altering either decision.

Adding a per-item field reddened the batch CLI's strict output schema, which is the projection working as designed: the payload is built by re-validating the engine's own serialisation precisely so an upstream field either arrives by name or fails loudly.
