---
tags:
  - '#exec'
  - '#agent-harness'
date: '2026-07-02'
modified: '2026-07-17'
body_hash: 'sha256:c5d07a641d6496cea94e2aaaed65a8bd9cd66625fe91c50e3225525fbd2faca3'
step_id: 'S04'
related:
  - "[[2026-07-02-agent-harness-plan]]"
---

# status:done (commit 6e7fc1629) - author the missing operator-lifecycle-ordering rule stating CALCULATE -> VERIFY -> FILE as an invariant

## Scope

- `src/aeat/_data/agent/rules/operator-lifecycle-ordering.md`

## Description

- Author the new Category C `operator-lifecycle-ordering` rule, the
  confirmed structural gap the rules-map design pass found (the
  `CALCULATE -> VERIFY -> FILE` invariant previously lived only in
  `coordinator.md` prose).
- State the ordering as an invariant: never verify before calculate, never
  export before a clean verify, never claim filed/reconciled before a human
  files.

## Outcome

Landed in commit `6e7fc1629`.

## Notes

None.
