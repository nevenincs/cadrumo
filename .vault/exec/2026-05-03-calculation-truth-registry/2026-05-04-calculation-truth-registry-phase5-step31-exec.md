---
tags:
  - '#exec'
  - '#calculation-truth-registry'
date: '2026-05-04'
modified: '2026-05-04'
related:
  - '[[2026-05-03-calculation-truth-registry-rebuild-plan]]'
---



# `calculation-truth-registry` `phase5` `step31`

Codified the calculation-authority evidence hierarchy as companion research and
ADR, then extended the existing rollout plan with the authority-tier framework.

- Created: `.vault/research/2026-05-04-calculation-authority-evidence-tiering-research.md`
- Created: `.vault/adr/2026-05-04-calculation-authority-evidence-tiering-adr.md`
- Modified: `.vault/plan/2026-05-03-calculation-truth-registry-rebuild-plan.md`

## Description

The new research records official BOE and AEAT references for the evidence
hierarchy. The companion ADR decides that BOE legal texts are legal authority,
AEAT instructions and manuals are official source guidance, AEAT Open/help
programs and true formula-form workbooks are executable parity evidence when
safe, and record designs are layout authority only.

The rollout plan now keeps this as an extended pre-modelo framework state. It
requires source evidence tiers, independent coverage ledgers for legal/source,
parity, and layout evidence, safe temporary XLS conversion, and validator
failures when a filing-grade calculation tries to rely on layout authority or
parity evidence as a substitute for legal basis.

## Tests

- `git diff --check` over the new research, ADR, execution record, and updated
  plan.
- Link-style audit confirmed no markdown links or body wiki-links were added to
  the new vault documents.
