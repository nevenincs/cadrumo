---
tags:
  - '#exec'
  - '#agent-harness'
date: '2026-06-30'
modified: '2026-07-17'
related:
  - "[[2026-06-30-agent-harness-plan]]"
---

# `agent-harness` `W05.P12` summary

Phase P12 authored the canonical workflow skill matrix. All five steps closed;
landed in commit `6e46cd93b`.

- Created: `src/aeat/_data/agent/skills/alta-contribuyente/SKILL.md`
- Created: `src/aeat/_data/agent/skills/llevar-libro/SKILL.md`
- Created: `src/aeat/_data/agent/skills/clasificar/SKILL.md`
- Created: `src/aeat/_data/agent/skills/exportar-declaracion/SKILL.md`
- Created: `src/aeat/_data/agent/skills/reconciliar/SKILL.md`

## Description

- S45: `alta-contribuyente` - onboard a taxpayer (create profile, capture identity,
  establish read access, confirm readiness).
- S46: `llevar-libro` - build and clean the ledger (import, review, correct, split,
  merge, check).
- S47: `clasificar` - classify and apportion (IRPF/IVA categories, allocation,
  ratios, prorrata, act on advisories).
- S48: `exportar-declaracion` - verify independently, export the fichero-BOE, and
  hand off for the human to file; never describe a local export as filed/accepted.
- S49: `reconciliar` - after the human files, pull the official justificante,
  compare, and record; acceptance only from official evidence.

## Outcome

The onboarding-to-reconcile happy path ships as executable playbooks. Each skill
cites only verbs that resolve against the live CLI surface (validated by the drift
gate, which now covers rules + personas + all skills).

## Notes

Each skill carries a `name`/`description` frontmatter for lazy progressive
disclosure and a success-assertion section grounding the operator in the JSON the
CLI returns rather than computed values.
