---
tags:
  - '#exec'
  - '#llm-package-split'
date: '2026-08-07'
modified: '2026-08-07'
body_schema: 'body-v1'
body_hash: 'sha256:f6b61dc6b3b67c3c0640a4257edeecada5f1a5d806b65075e38cf7441efb40e0'
step_id: 'S18'
related:
  - "[[2026-08-06-llm-package-split-plan]]"
---

# Replace the ZUGFeRD assertion that only checks for a German word with an exact field-level assertion against the fixture's printed values, red if a parser returning a wrong tax identifier still passes

## Scope

- `src/cadrumo/application/ledger/tests/test_evidence_corpus_parsing.py`

## Description

## Outcome

## Verification

## Notes

This record was reconstructed during a tracker reconciliation, not written by
the agent that executed the Step. The campaign landed roughly fifty Steps across
twenty commits while the plan tracker still read `0/83`, so the records were
recovered from the commit history rather than authored at execution time.

The Step is carried by commit `796914c2e3`, whose message cites it by identifier, and
its artifact was confirmed present at HEAD before the box was ticked. The full
step-to-commit mapping, the steps deliberately left unticked, and the
implementation-versus-plan deviation found along the way are in
`2026-08-07-llm-package-split-plan-tracker-reconciliation-audit`.

What this record does NOT carry is the executing agent's own account of the
work: the reasoning, the alternatives weighed, and the surprises met are in the
commit message and nowhere else. That is the cost of records written after the
fact, and it is why the gate wants them written at execution time.
