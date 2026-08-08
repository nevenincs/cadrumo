---
tags:
  - '#exec'
  - '#unstructured-document-ingestion'
date: '2026-08-08'
modified: '2026-08-08'
body_schema: 'body-v1'
body_hash: 'sha256:4412a8ca506717406da2affd6aac8eb806a4ecc079ebdb8b0752a095eabd55a6'
step_id: 'S52'
related:
  - "[[2026-08-07-unstructured-document-ingestion-plan]]"
---

# Add the typed transport retry policy with exponential backoff, jitter and a bounded budget scoped to transient failures only, never retrying schema, contention, consent or capability refusals, gated by tests against a real local HTTP server exhibiting each failure shape

## Scope

- `src/cadrumo/llm/_client.py`

## Description

- Split a transient transport error out of the general provider error, and route the connection-failure and 5xx raise sites at it in the shared transport helper and in the vendor SDK adapter.
- Add its registry row as retryable, flip the general provider error to non-retryable, and author its four locale values.
- Add the typed retry policy (attempt bound, exponential backoff, jitter, wall-clock budget) as data on the client.
- Derive retryability from the registered error code rather than from a list, failing closed for anything unregistered.
- Run the retry loop inside the admission slot, re-sending the identical request and never re-resolving the provider.

## Outcome

Only a dispatch that never reached a decision is re-sent. A 4xx, a malformed 2xx body, a consent refusal, a capability refusal, an occupancy refusal and a storage failure are left alone; a 5xx, a dropped connection, a read timeout and a rate limit are retried within a bounded attempt count and a bounded wall clock.

The eligibility set is derived, not listed. Every error class in this project must carry a registered error code, and that record already declares retryability for the operator-facing envelope, so a new failure class cannot exist without answering the question. A hand-kept set is the shape that has already shipped here carrying half its members. Anything outside the taxonomy is not retryable, which is the fail-closed direction.

Retries hold the on-host slot across their waits. Releasing it would let a second request take the arena and convert this one's next attempt into a busy refusal, turning a transient failure into a different refusal for no reason.

## Verification

uv run --no-sync pytest src/cadrumo/llm/tests/test_transport_retry_policy.py -m unit -p no:randomly -q
    18 passed in 44.63s

Every dispatch case runs against a real loopback HTTP server scripted to exhibit one genuine failure shape, and asserts how many requests actually arrived, because only the receiving end can answer whether something was sent again.

Proven by three mutations from external plugins. Declaring everything retryable turned the two scoping proofs red and left the rest green; declaring nothing retryable turned the four retry proofs red and left the scoping proofs green; declaring the consent refusal retryable in the taxonomy itself turned exactly the two assertions guarding that property red. Opposite mutations producing opposite, non-overlapping failures is what makes the classification measured rather than assumed.

## Notes

The governing decision record asks for the policy to be visible in the request record. It is data on the client and appears in the retry log line, but it is not a field on the persisted run record: adding one would change a strict persisted model owned by another package and would pull its roundtrip coverage into this Step. Reported to the lead as a scoping deviation rather than absorbed silently.

The contention refusal named in the row has no error class yet, because the Step wiring contention detection into the dispatch point has not landed. It is covered here by a property rather than by name: every retryable class must be a transport-boundary failure, so a contention refusal cannot become retryable without redding this gate.
