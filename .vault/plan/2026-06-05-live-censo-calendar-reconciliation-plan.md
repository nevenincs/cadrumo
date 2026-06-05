---
tags:
  - '#plan'
  - '#live-censo-calendar-reconciliation'
date: '2026-06-05'
tier: L3
related:
  - '[[2026-06-05-live-censo-calendar-reconciliation-reference]]'
  - '[[2026-06-05-calendar-filing-semantics-plan]]'
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

# `live-censo-calendar-reconciliation` `implementation` plan

## Wave `W01` - censo taxpayer-model bridge

Make censo apply produce defensible taxpayer-model facts that the existing calendar projection already understands.

### Phase `W01.P01` - censo-derived facts

TODO: Phase intent paragraph required by the convention ADR.

- [x] `W01.P01.S01` - Add censo/profile taxpayer fact derivation; `src/aeat/application/user_profile/_censo_sync.py`.
- [x] `W01.P01.S02` - Add real-behavior service and calendar tests for censo-derived obligations; `src/aeat/application/user_profile/tests/test_censo_sync.py`.

## Wave `W02` - live verification and closeout

Verify the CLI path from censo refresh/apply to calendar, including authenticated live-read attempts and explicit external-auth blockers.

### Phase `W02.P02` - gates and live checks

TODO: Phase intent paragraph required by the convention ADR.

- [ ] `W02.P02.S03` - Run focused lint/tests plus live censo/calendar CLI verification; `.vault/exec/2026-06-05-live-censo-calendar-reconciliation`.
- [ ] `W02.P02.S04` - Run code review and persist audit; `.vault/audit/2026-06-05-live-censo-calendar-reconciliation-code-review-audit.md`.

## Description

This plan closes the explicit live-censo calendar gap: Modelo obligations must derive from the taxpayer's legal situation, and the calendar must prove whether it used live censo-backed facts, profile facts, or refused because the necessary facts were not present.

## Verification

- A censo snapshot with DNI/NIE-backed profile identity and IAE epigraph applies derived taxpayer facts for natural-person economic activity.
- The derived facts make `projection_for_taxpayer` complete enough for the overview calendar to enumerate Modelo obligations.
- A censo snapshot without IAE/taxpayer-axis evidence does not silently infer obligations.
- Live `config profile censo refresh` is attempted and the result or authenticated external blocker is recorded.
- Focused tests and lint pass.
