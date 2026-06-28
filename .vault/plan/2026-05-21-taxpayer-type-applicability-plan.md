---
tags:
  - '#plan'
  - '#cli-workflow-redesign'
date: '2026-05-21'
modified: '2026-05-21'
tier: L3
related:
  - '[[2026-05-21-taxpayer-type-applicability-adr]]'
  - '[[2026-05-21-taxpayer-type-applicability-research]]'
  - '[[2026-05-21-persona-fleet-round3-findings-audit]]'
  - '[[2026-05-21-cli-testimonial-audit]]'
  - '[[2026-05-26-corporate-tax-runtime-plan]]'
---


# `cli-workflow-redesign` plan: taxpayer entity-type / regime / enrolment model

Evolving plan executing the accepted ADR, grounded by the taxpayer-type
applicability research. Objective: the profile carries a structured
three-axis taxpayer model - entity type, tax regime, special enrolments
- and modelo applicability, the filing calendar, calculation selection,
brackets, and special-rule activation all derive from it through
registry-grounded rules. The autónomo-by-default assumption is removed.

This is a regulated-behaviour change: no schema or engine wave lands
before its rules are grounded in BOE/AEAT authority. The research
document already grounds the three axes and flags the facts it could
not authoritatively confirm; those are verified against BOE article
text before encoding.

## Wave `W01` - schema: the three-axis taxpayer model

This wave lands the typed three-axis taxpayer model on the profile
schema - entity type, tax regime, and special enrolments - replacing
the autónomo-by-default assumption with explicit operator-declared
facts collected by the wizard.

### Phase `W01.P01` - schema implementation

Add the three typed axes to the profile schema and collect them in the
wizard, replacing the flat autónomo assumption with explicit
operator-declared facts.

- [x] `W01.P01.S01` - Add a typed entity_type axis covering natural person, legal entity, and attribution entity to the profile schema; `src/aeat/domain/profile`.
- [x] `W01.P01.S02` - Add the natural-person IRPF income-category set as typed facts; `src/aeat/domain/profile`.
- [x] `W01.P01.S03` - Model the tax-regime axis for IRPF estimación directa normal, simplificada, objetiva, and the IVA regime variants including REAGP; `src/aeat/domain/profile`.
- [x] `W01.P01.S04` - Model the special-enrolment axis covering SII / REDEME, recargo de equivalencia, and OSS/IOSS; `src/aeat/domain/profile`.
- [x] `W01.P01.S05` - Rename AutonomoProfile to a name true for every entity type and collect the three axes in the wizard in plain operator language; `src/aeat/domain/profile`.
- [x] `W01.P01.S06` - Add roundtrip and anti-tautology tests for the new typed profile facts; `src/aeat/domain/profile`.

## Wave `W02` - derivation engine

This wave rewrites the overview applicability engine so every modelo
verdict, the filing calendar, calculation selection, and bracket
resolution derive from the taxpayer model rather than the autónomo
default, with an undeclared model yielding an explicit incomplete
answer instead of a confident wrong obligation.

### Phase `W02.P02` - engine rewrite

Rewrite applicability derivation to consume the taxpayer model via
registry rules, removing the autónomo default and surfacing an explicit
incomplete verdict when the model is undeclared.

- [x] `W02.P02.S07` - Rewrite the overview applicability engine to derive each modelo applicable verdict from the taxpayer model via registry rules and remove the autónomo default; `src/aeat/application/overview`.
- [x] `W02.P02.S08` - Derive the filing calendar, calculation selection, and bracket/rate resolution from the taxpayer model; `src/aeat/application/overview`.
- [x] `W02.P02.S09` - Yield an explicit incomplete applicability answer for an undeclared taxpayer model rather than a confident wrong obligation; `src/aeat/application/overview`.
- [x] `W02.P02.S10` - Add tests proving a landlord, a salaried-only taxpayer, a pensioner, and a sociedad limitada each receive the correct modelo set; `src/aeat/application/overview`.

## Wave `W03` - registry rules and grounding

This wave registers the BOE-grounded registry data the derivation
engine consumes - per-entity and per-regime modelo applicability
rules, the missing deadline windows, and the bracket/rate schedules
per entity type - each carrying its legal references.

### Phase `W03.P03` - registry encoding

Encode BOE-grounded per-entity and per-regime applicability rules,
deadline windows, and bracket/rate schedules into the registry, each
carrying legal_refs traceable to the authoritative BOE article.

- [x] `W03.P03.S11` - Register per-entity and per-regime modelo applicability rules each carrying legal_refs; `src/aeat/domain/calculations/registry`.
- [x] `W03.P03.S12` - Register the missing Modelo 100, 303, and 347 deadline windows and the corporate Modelo 200/202 calendar verified against BOE article text; `src/aeat/domain/calculations/registry`.
- [x] `W03.P03.S13` - Register the bracket/rate schedules per entity type covering IRPF tarifa and IS rate schedule with legal_refs; `src/aeat/domain/calculations/registry`.

## Child ADRs (spawn before their dependent waves)

- **Corporate-entity calculation model** - the IS rate schedule,
  Modelo 200/202 calculation routing, and attribution-regime
  pass-through. Needed before W02.P02.S08 / W03.P03.S13 for legal entities.
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

## Follow-on plans

Two real follow-on workstreams emerged during execution and are tracked
in their own binding plans rather than retrofitting them into the
already-landed Steps of this plan.

The micro-empresa bracketed IS rate dispatch and the new-entity
first-two-profit-periods 15 percent rate need a new bracket-by-entity-
type calculation-runtime op and a restructured Modelo 200 cuota-integra
formula; the same INCN profile fact also gates the Modelo 202 modality
split per the corporate-entity child ADR. The corrected
`tipo-gravamen-pyme` LIS Art. 29 bracket data landed in `W03.P03.S13`
so no consumer reads a wrong flat value meanwhile, and a micro-empresa
profile fails loudly under the current scalar dispatch op rather than
computing a wrong cuota. The runtime extension is the corporate-tax-
runtime follow-on plan dated 2026-05-26 carrying the
`#corporate-tax-runtime` feature tag and linked from the `related:`
frontmatter above.

The Modelo 200 and 202 corporate-calendar deadline windows are in
foreign-flight at the time of this plan's closure; `W03.P03.S12` above
captures the R1 Modelo 100 / 303 / 347 windows that were the priority
emerging from round-3 testimonials. The corporate-calendar Modelo 202
1P / 2P / 3P windows are being registered by a parallel campaign and
will land outside this plan's scope.
