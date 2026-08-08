---
tags:
  - '#exec'
  - '#unstructured-document-ingestion'
date: '2026-08-08'
modified: '2026-08-08'
body_schema: 'body-v1'
body_hash: 'sha256:d07c6fae868b1f2b0034707b627d07796e8816d8891dc8bff80bc45a3ef34b29'
step_id: 'S58'
related:
  - "[[2026-08-07-unstructured-document-ingestion-plan]]"
---




# Bound in-process inference concurrency (default one) with a typed busy refusal or deterministic queueing, gated by a two-concurrent-request test proving exactly one proceeds

## Scope

- `src/cadrumo/llm/_client.py`

## Description

- Add the process-wide on-host inference arena to the client module: a loop-agnostic occupancy bound sized from settings at first use and shared by every client in the process.
- Add the local inference concurrency setting, default one, carrying the refusal-not-queueing rationale on the field.
- Add the busy error to the taxonomy, its registry row and its four locale values: refusal category, non-retryable, suggesting the check verb.
- Hold a slot around the adapter call only, scoped to on-host providers through the existing off-host predicate, released on every exit path.

## Outcome

A second concurrent on-host request is refused with a typed busy error rather than queued or admitted. Refusal was chosen over queueing on the failure direction: a queue does not help when the bound is too permissive, and when the bound is right a waiter holds its decoded pages in the memory already under pressure and then runs against headroom measured before it waited. The refusal is synchronous and observable, and the caller retries after quiesce.

The bound is a process singleton because the resource it protects is the machine, not the client object; production builds one client per caller, so a per-instance bound would hold for neither. It binds on-host dispatch only, derived from the same predicate the consent gate uses, because an off-host dispatch occupies none of this machine's device memory.

## Verification

uv run --no-sync pytest src/cadrumo/llm/tests/test_on_host_inference_admission.py -m unit -p no:randomly -q
    5 passed in 17.50s

    uv run --no-sync pytest src/cadrumo/llm -m unit -p no:randomly -q
    409 passed in 105.36s (0:01:45)

The gate drives two genuinely concurrent requests through the production client and a real loopback runtime that holds the first request open until the test releases it, so the contention is established by the server rather than by a sleep.

Proven by mutation from an external pytest plugin, with nothing under the source tree changed: replacing the admission context manager with an unbounded one turned five passes into three failures, while the two-slot positive control stayed green, so the green reading is about the bound rather than about everything failing.

## Notes

The permitted-path assertions were blocked for part of the run by a live defect outside this Step: the diagnostic redaction funnel's tax-identity rule matched a Z-suffixed UTC timestamp, so every response-cache write failed its own bind guard and every completion raised. Reported to the campaign lead and to the owning lane; a peer fix landed in the working tree and the gate then ran clean. Nothing here works around it.

The source landed through a tree-wide sweep commit rather than through a commit of mine, so this Step and the retry Step share one sweep commit rather than being separable.

