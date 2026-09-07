---
tags:
  - '#exec'
  - '#reachability-burndown'
date: '2026-09-06'
modified: '2026-09-07'
body_schema: 'body-v2'
body_hash: 'sha256:b62e71160a0eb9ff926a6e392ac6501a72eb440c842b1578c4f31f3fc9dc6e0c'
step_id: 'S71'
related:
  - "[[2026-09-04-reachability-burndown-plan]]"
---

# Wire the one true persistence gap and retire the three false ones: the workflow gate's draft builder now saves the approved draft through ModeloDraftRepository, so the review queue's draft rows, the workspace summary count and the CLI draft lookup finally read a store the application fills, and the approval-staleness lifecycle has a subject. Extending the detector to follow repository accessors and to count replace_observations as a write cleared the other three, leaving the declaration empty; enrol the gate as a just recipe and assert the live tree inside the test lane so it can fail CI.

## Scope

- `src/cadrumo/application/modelo/workflow_gate.py`
- `src/cadrumo/application/modelo/tests/test_file_flow_draft_persistence.py`
- `dev/quality/secure_store_write_path.py`
- `dev/quality/secure_store_write_path.toml`
- `dev/quality/tests/test_secure_store_write_path.py`
- `justfile`
- `dev/audit/reachability_classification.toml`

## Changes

- `M` `src/cadrumo/application/modelo/workflow_gate.py`
- `A` `src/cadrumo/application/modelo/tests/test_file_flow_draft_persistence.py`
- `M` `dev/quality/secure_store_write_path.py`
- `M` `dev/quality/secure_store_write_path.toml`
- `M` `dev/quality/tests/test_secure_store_write_path.py`
- `M` `justfile`
- `M` `dev/audit/reachability_classification.toml`
- `verify:` `python -m dev.quality.secure_store_write_path` exit 0 with an EMPTY
  declaration -- every secure store the application reads now has a writer
- `verify:` `pytest dev/quality/tests/test_secure_store_write_path.py` 21 passed
- `verify:` `pytest src/cadrumo/application/modelo/tests/test_file_flow_draft_persistence.py` passed
- `verify:` `pytest .../test_workflow_gate_error_boundary.py .../test_verification_substance_workflow.py` 13 passed
- `verify:` `ruff check` and `ty check` clean on every changed module
- `verify:` ledger validated by direct script -- 113 clusters, all cited paths resolve

## Notes

One of the four stores was genuinely unwritten, and it was the consequential one.
The workflow gate built a filing draft, approved it, handed it to preflight and
dropped it, so the encrypted filing-draft namespace had no writer at all while
three surfaces rendered from it. The builder now persists the approved draft
before returning it. `draft_id` is a content address, so re-running the gate over
unchanged inputs rewrites one row; the test asserts that, and asserts the store
is empty before the run so a pass cannot be inherited from something else.

A persistence failure raises rather than being swallowed. A filing artefact that
silently failed to durably exist is precisely the absence its readers cannot
distinguish from an empty workspace.

The other three were detector false positives, and finding them was the more
useful half of the step. Extending the detector to follow a repository accessor
-- a function whose return annotation names the repository, which is how a
lazily bucket-bound store is reached -- cleared the purchase-evidence store and
proved the new draft write at the same time. Counting `replace_observations` as
a write cleared both withholding stores, whose single shared persist helper the
aggregate CLI calls. Adding a verb to the list retired a claim that a
filing-grade aggregation was reading an empty store.

Enrolment was the other real gap: the gate was a module nobody invoked. It is now
a `check-secure-store-write-path` recipe and an assertion inside the test lane
that already collects `dev/quality/tests`.
