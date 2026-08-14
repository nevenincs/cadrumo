---
tags:
  - '#exec'
  - '#test-harness-sanity'
date: '2026-08-14'
modified: '2026-08-14'
body_schema: 'body-v1'
body_hash: 'sha256:50603c94d23d2a1419b9c1b1327bd300fbfc6d6b64ebd27edd3ee975316448dc'
step_id: 'S76'
related:
  - "[[2026-08-14-test-harness-sanity-plan]]"
---

# Replace previous-filing exception mutation with reachable real behavior

## Scope

- `src/cadrumo/application/calculations/tests/test_previous_filing_absence_versus_malformed.py`

## Description

- Remove the exception-type monkeypatch from previous-filing behavior tests.
- Retain real empty-repository absence, persisted incomplete-observation refusal, and public-resolver ambiguity coverage.
- Reconcile the module rationale to the reachable production branches.

## Outcome

Previous-filing absence and malformed-state semantics are now covered exclusively through real encrypted repositories and public typed inputs. No runtime alias or exception class is mutated, and no unique reachable contract branch was deleted.

## Notes

Independent review traced all three production branches and confirmed the removed test only exercised a hypothetical exception alias mutation. Ruff, diff integrity, and the monkeypatch inventory for this surface passed. The three focused behavior tests currently fail before reaching their assertions because the shared Modelo 130 snapshot rejects seven `agent_reviewed` legal references that require `operator_reviewed`; that external blocker is recorded without claiming a green behavior run.
