---
tags:
  - '#exec'
  - '#cli-authority-verb-conformance'
date: '2026-07-25'
modified: '2026-07-25'
body_hash: 'sha256:c7a645a325df9f33c1815b4936992aebf329636e23c298e12f3dd37181df4aaa'
step_id: 'S253'
related:
  - "[[2026-07-15-cli-authority-verb-conformance-plan]]"
---

# Prove suggestion, saturation, rejection, no-split, multi-child split, invocation-origin attribution, and CLI-route parity against real persistence and model subprocess boundaries

## Scope

- `src/cadrumo/application/ledger/tests/test_llm_reject.py`
- `src/cadrumo/application/ledger/tests/test_llm_saturation.py`
- `src/cadrumo/application/ledger/tests/test_llm_evidence_no_split.py`
- `src/cadrumo/application/ledger/tests/test_llm_evidence_split_apply.py`
- `src/cadrumo/entrypoints/cli/tests/`

## Description

- Enumerate the seven proof obligations this step names and match each to a shipped test.
- Confirm the tests exercise real persistence and the real model boundary rather than doubles.
- Run the LLM review suites at the current commit with the marker filter overridden so collection is non-empty.

## Outcome

Already satisfied. Closed as verified rather than re-implemented.

Every named obligation has a test. Suggestion application, saturation, rejection, the no-split refusal, the multi-child split, invocation-origin attribution and CLI-route parity are each covered, the last by two dedicated tests that drive the classify-apply and split-apply routes and compare them against the direct primitive. Origin attribution is proved twice over: one test asserts the auto-split origin's label is stamped on split children, a second asserts the `split --llm` origin stamps its own distinct label on the same workflow branch, which is the assertion that would fail if the two routes were ever collapsed onto one origin. A further test walks the whole enum and requires every origin to derive a distinct non-blank label, so adding an origin without a spelling fails rather than silently producing a blank audit label.

The refusal space is covered as well as the happy path. A split decision on a classification suggestion refuses, the two non-persisting terminals refuse durable execution, and a no-split verdict refuses a split decision. These matter more than the apply tests, because a wrong-primitive dispatch would otherwise write a real ledger mutation under the wrong audit label.

The tests are real-behaviour. They run against a real SQLite-backed encrypted catalogue and real event repositories, assert on persisted payloads read back from storage rather than on return values alone, and the reject tests confirm the transaction is left unmutated and still pending. The rejection assertion reads the persisted event payload's source command and compares it to the label the origin derives, so the audit trail is checked where it durably lands.

Run at the current commit across the six suites this step and its scope cite: 35 tests collected and passed, with the default marker filter overridden so an integration module could not select nothing and exit green.

No change was needed or made.

## Notes

Semantic CODE search is degraded and reports itself healthy, so the test inventory was assembled by direct read and grep rather than by search.

A bare path invocation of these suites is not a verification here: the default marker selects nothing for the integration modules and exits zero. The counts quoted above come from runs with the marker filter cleared, and a non-zero collected count was confirmed before reading the result.
