---
tags:
  - '#plan'
  - '#cli-testimonial'
date: '2026-05-21'
tier: L2
related:
  - '[[2026-05-20-testimonial-driven-cli-verification-playbook]]'
  - '[[2026-05-20-cli-persona-task-catalogue]]'
  - '[[2026-05-21-cross-campaign-hardening-persona-testimonial-re-audit]]'
---

<!-- LINK RULES:
     - [[wiki-links]] are ONLY for .vault/ documents in the
       related: field above.
     - The related: field carries the AUTHORISING documents
       (ADR, research, reference, prior plan) for every Step in
       this plan. Steps inherit this chain; per-row reference
       footers do not exist.
     - NEVER use [[wiki-links]] or markdown links in the
       document body. -->

# `fresh-cli-persona-testimonial-wave` plan

### Phase `P01` - scope and briefing

Define the fresh wave and make the persona instructions reproducible.

- [x] `P01.S01` - write fresh persona wave plan and briefs; `.vault/plan .vault/audit`.
- [x] `P01.S02` - validate the fresh wave plan structure; `.vault/plan`.

### Phase `P02` - persona execution

Run independent CLI-only persona passes in isolated scratch state.

- [x] `P02.S03` - run sole-professional profile and Modelo 130 persona; `.vault/audit`.
- [x] `P02.S04` - run company-administrator Modelo 303 and company-shape persona; `.vault/audit`.
- [x] `P02.S05` - run landlord Renta and rental-income persona; `.vault/audit`.
- [x] `P02.S06` - run payroll-retention Modelo 111 persona; `.vault/audit`.
- [x] `P02.S07` - run correction and filing-handoff persona; `.vault/audit`.
- [x] `P02.S08` - run legal/manual explainability persona; `.vault/audit`.

### Phase `P03` - consolidation and reproduction

Separate testimonial friction from verified defects.

- [x] `P03.S09` - consolidate persona feedback into a severity-graded inventory; `.vault/audit`.
- [x] `P03.S10` - reproduce every blocker and major finding directly; `.vault/audit`.

### Phase `P04` - follow-up wave

Convert verified findings into executable repair work.

- [x] `P04.S11` - write the follow-up repair plan for verified findings; `.vault/plan`.
- [x] `P04.S12` - run locale, plan, and diff gates for the fresh wave artifacts; `.vault src/aeat`.
