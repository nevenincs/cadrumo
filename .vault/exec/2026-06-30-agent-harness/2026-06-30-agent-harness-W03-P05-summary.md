---
tags:
  - '#exec'
  - '#agent-harness'
date: '2026-06-30'
modified: '2026-06-30'
related:
  - "[[2026-06-30-agent-harness-plan]]"
---

# `agent-harness` `W03.P05` summary

Phase P05 authored the minimal tax-advisor persona slice. All three steps closed;
landed in commit `2c8020cf5`.

- Created: `src/aeat/_data/agent/personas/coordinator.md`
- Created: `src/aeat/_data/agent/personas/modelo-preparer.md`
- Created: `src/aeat/_data/agent/personas/verifier.md`

## Description

- S19: Coordinator persona - owns the taxpayer conversation and sequencing,
  delegates hands-on steps, holds provenance, surfaces warnings and exit-1
  verdicts, never computes a value, never files. Read-only/orchestration scope.
- S20: Modelo-preparer persona - creates and calculates a work unit addressed by
  modelo/year/period (law-determined revision), reads casillas with their
  grounding, hands the revision to the verifier; never verifies its own work.
  Modelo-family mutating scope.
- S21: Verifier persona - runs `aeat app modelo work verify` as an independent
  step, treats exit 1 as a verdict, applies the under-declaration check, reports
  findings without rationalising them away. Read/verify scope.

## Outcome

The three personas ship under the harness data tree and are read by the
`aeat.agent` accessor. Every CLI verb they cite resolves against the live surface
(the rule-surface drift gate, extended in P07, validates persona verbs).

## Notes

Tool scope is documented in prose per persona (mutability tier); enforcement of
the scope is the MCP layer's job in a later wave.
