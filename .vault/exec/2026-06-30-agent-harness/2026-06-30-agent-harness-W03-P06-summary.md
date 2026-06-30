---
tags:
  - '#exec'
  - '#agent-harness'
date: '2026-06-30'
modified: '2026-06-30'
related:
  - "[[2026-06-30-agent-harness-plan]]"
---

# `agent-harness` `W03.P06` summary

Phase P06 authored the modelo-130 preparation skill. Both steps closed; landed in
commit `2c8020cf5`.

- Created: `src/aeat/_data/agent/skills/preparar-modelo-130/SKILL.md`
- Created: `src/aeat/_data/agent/skills/preparar-modelo-130/reference/casillas.md`

## Description

- S22: The `preparar-modelo-130` SKILL.md - an executable playbook with
  preconditions (active profile, built and classified ledger, known year/period),
  a numbered command sequence (describe/casillas, work create, calculate, read
  revision, independent verify, export, reconcile pull), JSON success assertions
  (status success/warning never error, rendimiento consistency, the
  positive-income/zero-instalment suspicion check, verbatim values with
  provenance), and the produce/verify/handoff boundary.
- S23: A progressive-disclosure casilla reference that orients the operator on the
  direct-estimation block (ingresos, gastos, rendimiento, instalment, prior
  instalments, retenciones, result) while deferring to the registry
  (`aeat app modelo casillas`) as the authority and forbidding hand-reported
  values.

## Outcome

The skill ships under the harness tree and is read by the `aeat.agent` accessor;
the golden eval (P07) asserts the modelo-130 trajectory is consistent with this
playbook, and the drift gate confirms every cited verb resolves.

## Notes

The reference deliberately states no figures: per the legal-grounding discipline,
casilla values come only from the CLI calculation, never from authored prose.
