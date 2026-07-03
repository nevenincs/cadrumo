---
tags:
  - '#exec'
  - '#agent-harness-refoundation'
date: '2026-07-02'
modified: '2026-07-02'
step_id: 'S65'
related:
  - "[[2026-07-02-agent-harness-refoundation-plan]]"
---

# Author the regularizar-atrasos skill sequencing the overview backlog past-due and recargo extemporaneo surface

## Scope

- `src/aeat/_data/agent/skills/regularizar-atrasos/SKILL.md`

## Description

- Ground the skill in the live CLI surface: confirm `aeat app overview backlog`
  (`_overview.py`, `late_count`/items/warnings/coverage lines), the work-unit
  overdue rendering (`_modelo_rendering.py`: `days_overdue`, `recargo_band`,
  `recargo_pct`, plazo-vencido notice), and `aeat app modelo work amend`
  (complementaria path) before citing any of them.
- Author `src/aeat/_data/agent/skills/regularizar-atrasos/SKILL.md` as the
  first WHEN-layer life-situation skill: `applies_when.temporal_trigger =
  backlog_overdue`; oldest-first sequencing; verbatim-relay rule for every
  recargo/days-overdue figure (LGT art. 27 is CLI-owned law); ledger-clean
  gate before any catch-up calculation; missing-vs-wrong routing split to
  `rectificar-declaracion`; requerimiento-received case routed out to a human
  professional; per-item reconciliation as the only official-acceptance
  authority.
- Validate against the rule-surface drift gate and the applies_when metadata
  gate; commit with explicit pathspec.

## Outcome

Skill authored by the coordinator per the operator directive that all skill
content is coordinator-authored. Gates green at commit: rule-surface
conformance (every cited verb resolves) and skill applies_when validation,
10 passed. Commit `8eea7a374`, exactly one file.

## Notes

The shared index held a peer campaign's staged justificante moves at commit
time; the explicit-pathspec commit took only this Step's file, leaving the
peer's staged work untouched. The art. 27.5 prompt-payment reduction is
deliberately NOT taught by the skill (the CLI does not model it); the skill
instead directs the taxpayer to the reconciled justificante as the recargo
authority — the honest posture until the fidelity gap closes.
