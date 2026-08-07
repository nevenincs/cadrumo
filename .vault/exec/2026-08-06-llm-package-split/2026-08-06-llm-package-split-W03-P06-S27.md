---
tags:
  - '#exec'
  - '#llm-package-split'
date: '2026-08-07'
modified: '2026-08-07'
body_schema: 'body-v1'
body_hash: 'sha256:6d2b2a9613a41e0d901d2370efacce088529bf5fade72d7b2d57ca45722b89a2'
step_id: 'S27'
related:
  - "[[2026-08-06-llm-package-split-plan]]"
---

# Refuse a malformed payload at the core boundary rather than coercing it and pin the refusal by test, red if a malformed payload is silently normalised into a valid one

## Scope

- `src/cadrumo/application/ledger/`

## Description

## Outcome

## Verification

## Notes

This record was reconstructed during a tracker reconciliation, not written by
the agent that executed the Step. The campaign landed roughly fifty Steps across
twenty commits while the plan tracker still read `0/83`, so the records were
recovered from the commit history rather than authored at execution time.

The Step is carried by commit `cdb874c245`, whose message cites it by identifier, and
its artifact was confirmed present at HEAD before the box was ticked. The full
step-to-commit mapping, the steps deliberately left unticked, and the
implementation-versus-plan deviation found along the way are in
`2026-08-07-llm-package-split-plan-tracker-reconciliation-audit`.

What this record does NOT carry is the executing agent's own account of the
work: the reasoning, the alternatives weighed, and the surprises met are in the
commit message and nowhere else. That is the cost of records written after the
fact, and it is why the gate wants them written at execution time.
