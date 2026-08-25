---
tags:
  - '#exec'
  - '#dehu-notification-legal-effect'
date: '2026-08-13'
modified: '2026-08-13'
body_schema: 'body-v1'
body_hash: 'sha256:b5ac7aceb0e8c996454f2fc9573db365bcc27913d7043a964528eebfcd7cdac0'
step_id: 'S09'
related:
  - "[[2026-08-07-dehu-notification-legal-effect-plan]]"
---

# Run the targeted suites sequentially, core tests, the registry legal and catalogue tests, application overview tests and entrypoints cli tests, plus vaultspec-core vault check all and the locales scaffold --check gate, capture full output to a log file per aeat-local-execution, and triage any red signature as owner-surface or unrelated peer churn before closing this Step

## Scope

- `no production files`
- `verification only`

## Description

- Ground the terminal verification against the accepted ADR, its reference,
  semantic RAG results, and whole canonical epicentres.
- Confirm the single canonical service-state resolver, overview actionability
  predicate, and CLI deemed-service Notice composer with exact-symbol caller
  searches.
- Run the core, registry legal/catalogue, overview, and CLI suites sequentially
  with full output captured to the local verification log.
- Rerun the registry legal/catalogue subset serially after its parallel run
  reported concurrent registry fingerprint churn.
- Review the completed work formally; resolve the discovered message-only
  event-model invariant at `OverviewCalendarEvent` and add the real DTO
  refusal regression.
- Recheck the repair independently, then rerun its owner-surface tests and
  the terminal vault and locale gates.

## Outcome

The DEHu owner surface is verified: the direct service-state and payload
regression run passed 15 tests, the initial serial legal/catalogue rerun passed
158 tests, and the independent repair review passed. A non-message event can
no longer carry `RECHAZO_TACITO`, while the real message projection still
round-trips that state.

`vault check all` exited zero. The final full target-suite logs contain no
untriaged DEHu failure: core reported 9 unrelated global ratchet and concurrent
registry-load signatures; registry legal/catalogue reported 63 failures from a
concurrently introduced duplicate `real-decreto-ley-7-2024:art-11` catalogue
id; overview reported 14 unrelated action-contract/data-prep/regime failures;
and CLI reported 5 unrelated ledger, module-size, profile-recovery, and
concurrent-registry signatures. The final locale scaffold check reported only
another live campaign's missing `application.live.*` keys and obsolete
overview-status extras. These are peer-churn blockers outside this Step's
canonical owners.

## Notes

The shared worktree changed during verification. The initial parallel registry
run was invalid because its loader reported a directory change while
fingerprinting; the serial legal/catalogue rerun supplied the valid DEHu
evidence before later unrelated registry and locale work made the tree red
again. No destructive Git operation or peer-worktree mutation was used.
