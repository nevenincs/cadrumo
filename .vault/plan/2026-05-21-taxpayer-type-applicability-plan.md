---
tags:
  - '#plan'
  - '#cli-workflow-redesign'
date: '2026-05-21'
tier: L3
related:
  - "[[2026-05-21-taxpayer-type-applicability-adr]]"
  - "[[2026-05-21-taxpayer-type-applicability-research]]"
  - "[[2026-05-21-persona-fleet-round3-findings]]"
---

# `cli-workflow-redesign` plan: taxpayer entity-type / regime / enrolment model

Evolving plan executing the accepted ADR
`[[2026-05-21-taxpayer-type-applicability-adr]]`, grounded by
`[[2026-05-21-taxpayer-type-applicability-research]]`.

Objective: the profile carries a structured three-axis taxpayer model
- entity type, tax regime, special enrolments - and modelo
applicability, the filing calendar, calculation selection, brackets,
and special-rule activation all derive from it through
registry-grounded rules. The autónomo-by-default assumption is removed.

This is a regulated-behaviour change: no schema or engine wave lands
before its rules are grounded in BOE/AEAT authority. The research
document already grounds the three axes and flags the facts it could
not authoritatively confirm; those are verified against BOE article
text before encoding.

## Wave `W01` - schema: the three-axis taxpayer model

- [ ] `W01.S01` - add a typed `entity_type` to the profile schema:
  natural person vs legal entity (S.L., S.A., cooperativa, ...) vs
  attribution entity (comunidad de bienes, sociedad civil sin objeto
  mercantil).
- [ ] `W01.S02` - add the natural-person IRPF income-category set
  (actividad económica, trabajo, capital inmobiliario, capital
  mobiliario, ganancias patrimoniales, pensión) as typed facts.
- [ ] `W01.S03` - model the tax-regime axis: IRPF estimación directa
  normal / simplificada / objetiva; the IVA regime variants incl.
  REAGP.
- [ ] `W01.S04` - model the special-enrolment axis (SII / REDEME,
  recargo de equivalencia, OSS/IOSS, ...).
- [ ] `W01.S05` - rename `AutonomoProfile` to a name that is true for
  every entity type; the wizard collects the three axes in plain
  operator language.
- [ ] `W01.S06` - roundtrip + anti-tautology tests for the new typed
  profile facts.

## Wave `W02` - derivation engine

- [ ] `W02.S07` - rewrite the `overview` applicability engine to
  derive each modelo's `applicable` verdict from the taxpayer model
  via registry rules; remove the autónomo default.
- [ ] `W02.S08` - derive the filing calendar, calculation selection,
  and bracket/rate resolution from the taxpayer model.
- [ ] `W02.S09` - an undeclared taxpayer model yields an explicit
  `incomplete` applicability answer - never a confident wrong
  obligation.
- [ ] `W02.S10` - tests proving a landlord, a salaried-only taxpayer,
  a pensioner, and a sociedad limitada each get the correct modelo
  set (e.g. landlord: 100, not 130; S.L.: 200/202, not 100/130).

## Wave `W03` - registry rules and grounding

- [ ] `W03.S11` - register per-entity / per-regime modelo
  applicability rules, each carrying `legal_refs`.
- [ ] `W03.S12` - register the missing Modelo 100 / 303 / 347
  deadline windows (round-3 finding R1) and the corporate calendar
  (Modelo 200/202), verified against BOE article text.
- [ ] `W03.S13` - register the bracket/rate schedules per entity type
  (IRPF tarifa vs IS rate schedule), with `legal_refs`.

## Child ADRs (spawn before their dependent waves)

- **Corporate-entity calculation model** - the IS rate schedule,
  Modelo 200/202 calculation routing, and attribution-regime
  pass-through. Needed before W02.S08 / W03.S13 for legal entities.
- **SII model** - the near-real-time ledger-submission obligation
  class, which the deadline engine cannot express today. Needs the
  BOE-grounded SII facts from the research doc; spawn before any SII
  enrolment behaviour lands.

## Dependencies and cadence

- Hard dependency on the registry track for W03 rule data and the R1
  deadline windows.
- The research doc's "limits of grounding" list is verified against
  BOE before W03 encoding.
- Each wave gates on a green suite and lands real-behavior tests;
  each closes with a `.vault/audit/` note.
- Owner approval of this plan is required before W01 execution; the
  ADR is accepted, the plan is the next gate.
