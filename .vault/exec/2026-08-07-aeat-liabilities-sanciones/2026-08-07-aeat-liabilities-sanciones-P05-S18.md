---
tags:
  - '#exec'
  - '#aeat-liabilities-sanciones'
date: '2026-08-12'
modified: '2026-08-12'
body_schema: 'body-v1'
body_hash: 'sha256:9e0e9a9cd8ebf401ca71d90038ab32c93ddb311c62c978d9e4f6ebcfcee4cb64'
step_id: 'S18'
related:
  - "[[2026-08-07-aeat-liabilities-sanciones-plan]]"
---

# Add deudas pull to the operator-orientation agent-harness document alongside expedientes pull and notifications pull in the same commit as the verb, verified by test_documented_command_conformance

## Scope

- `src/cadrumo/_data/agent/rules/cadrumo-operator-orientation-routing.md`

## Description

- Not implemented. Blocked on S16's verb; documenting it earlier would fail the
  row's own conformance gate.

## Outcome

**DEFERRED CARRY-FORWARD. The harness document was not swept.**

The operator-orientation harness may cite only verbs that resolve against the
live operator-surface manifest. Documenting `deudas pull` before it exists would
hand the agent operator a dead instruction it cannot recover from, and would red
`test_documented_command_conformance` — the gate this row names as its own
verification.

So the row is not merely blocked, it is currently un-performable: doing it would
break the gate that proves it was done correctly.

## Notes

Land the harness line in the same commit as the verb, alongside the existing
`expedientes pull` and `notifications pull` entries.
