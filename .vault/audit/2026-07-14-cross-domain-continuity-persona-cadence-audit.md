---
tags:
  - '#audit'
  - '#cross-domain-continuity'
date: '2026-07-14'
modified: '2026-07-17'
related:
  - "[[2026-05-26-cross-domain-continuity-plan]]"
  - "[[2026-07-10-cross-domain-continuity-audit]]"
  - "[[2026-07-11-cross-domain-continuity-audit]]"
  - "[[2026-07-12-cross-domain-continuity-audit]]"
---

# `cross-domain-continuity` audit: `quarterly persona cadence establishment`

## Scope

This audit establishes `W11.P59.S337`, the third durable maintenance gate the
plan requires alongside `S335` (vault structural-drift CI gate) and `S336`
(ledger + storage roundtrip suite gate). Those two gates are mechanical and
already run on every commit via `.github/workflows/durable-maintenance-gates.yml`.
`S337` is different in kind: it is a scheduled, LLM-persona-driven UX and
correctness sweep that no fixed test suite can substitute for, because it
exercises operator judgment (does the CLI output make sense to a human tax
filer?) rather than a fixed assertion. This document is the schedule-establishment
artifact that closes the gap: it fixes the cadence, names the rotation of
persona shapes, and records the most-recent round as the cadence's first
anchor point, exactly as the `S335`/`S336` workflow file established their
running mechanism rather than claiming perpetual completion.

## Findings

### cadence-not-yet-scheduled | low | no standing quarterly schedule existed before this audit

Before this document, `S337` had no schedule-establishment artifact: no cron,
no recorded cadence, no named persona rotation. The 2026-07-10 checkpoint audit
correctly refused to close the step on that basis, since a step that only
claims a future intention with nothing on record is not closable. This audit
supplies the missing schedule.

### existing-persona-rounds-already-exceed-the-three-shape-floor | low | recent rounds already rotate more than three distinct tax shapes

The `2026-06-30` round (`cli-persona-testimonials-audit` and its `w05-closure`
companion) exercised autónomo/actividad-económica (Marc, IT design), a
non-business natural-person profile (Pere), and the ledger/profile-identity
boundary personas. The `2026-07-11` Wave-9 terminal round exercised attribution
entities, objective-estimation, salary, pension, and foreign-pension personas
(five distinct shapes in one round). The `2026-07-12` Wave-10 terminal round
exercised registry-discovery personas across M100, M111, M131, M180, M200,
M202, M349, and M390, including the M232 applicability-suppression case. Every
round already on record exceeds the plan's "3+ shapes" floor; the cadence
schedule below formalises rotating a comparable spread going forward rather
than inventing a new requirement.

## Recommendations

### quarterly cadence schedule

- **Cadence:** one full persona re-run round per calendar quarter, scheduled
  (not ad-hoc), producing exactly one new `.vault/audit/` document per round
  per the `W11.P59.S193` one-audit-per-terminus convention already governing
  this plan.
- **Anchor round:** the `2026-06-30` round is the cadence's first anchor. The
  Wave-9 (`2026-07-11`) and Wave-10 (`2026-07-12`) terminal rounds are
  additional in-cadence rounds landing inside the same quarter (Wave termini
  fire more often than quarterly during active execution, per `S192`'s stated
  "roughly weekly during execution, monthly in maintenance" cadence — the
  quarterly floor in `S337` is the maintenance-mode minimum once the campaign
  is at rest, not a ceiling during active execution).
- **Next due date:** 2026-09-30 (one quarter after the 2026-06-30 anchor),
  or sooner if a Wave terminus or a new BLOCKER triggers an earlier round
  under `S192`/`S196`.
- **Required persona-shape rotation (minimum 3 per round, drawn from this
  pool, rotating which three are exercised each quarter):** autónomo /
  actividad económica (estimación directa or módulos); atribución de rentas
  entity; salaried employment plus pension or foreign-pension income; sociedad
  (Impuesto sobre Sociedades) filer; a non-business natural person with no
  filing obligation (the negative-case persona). Each round's audit document
  must name which shapes it exercised, per the existing convention already
  followed by every round on record.
- **Owner and trigger:** the coordinator dispatches the round; a round is
  overdue if the next-due date passes with no new persona-round audit
  document recorded for the plan. An overdue round is itself a finding for
  the next checkpoint audit, not a silent lapse.
