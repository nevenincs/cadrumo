---
step_id: S110
tags:
  - '#exec'
  - '#core-authority'
date: '2026-05-31'
modified: '2026-05-31'
related:
  - "[[2026-05-31-core-authority-plan]]"
  - "[[2026-05-31-core-authority-adr]]"
  - "[[2026-05-31-core-authority-audit]]"
---

# core-authority W13.P32.S110 step record

## Step

Update the audit dispatch brief template (`.vaultspec/rules/rules/aeat-swarm-audit-cadence.md`)
to mandate a substitutability pre-filter for any audit brief using the "X where Y exists"
pattern.

## Amendment

Added paragraph to `aeat-swarm-audit-cadence` rule:

> Apply the substitutability pre-filter before flagging any "X where Y exists" violation.
> Any audit brief that identifies a site X where a canonical alternative Y exists must
> require the auditor to verify that Y's constraint shape is a superset of (more permissive
> than) X's current constraint before classifying X as actionable.

This addresses AUDITPIPE-008: the PROMOTE-001 audit had a 96% false-positive rate because
the alias-existence check did not verify constraint-shape compatibility.

## Files touched

- `.vaultspec/rules/rules/aeat-swarm-audit-cadence.md` — added substitutability pre-filter mandate
- `.claude/rules/aeat-swarm-audit-cadence.md` — synced from vaultspec source
- `.gemini/rules/aeat-swarm-audit-cadence.md` — synced
- `.agents/rules/aeat-swarm-audit-cadence.md` — synced
- `.codex/rules/aeat-swarm-audit-cadence.md` — synced
