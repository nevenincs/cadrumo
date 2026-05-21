---
tags:
  - '#adr'
  - '#cli-workflow-redesign'
date: '2026-05-21'
related:
  - "[[2026-05-21-persona-fleet-round3-findings]]"
  - "[[2026-05-12-cli-workflow-redesign-adr]]"
  - "[[2026-05-21-work-verify-deadline-independence-adr]]"
---

# `cli-workflow-redesign` adr: `The profile carries a structured taxpayer income-type, and modelo applicability derives from it` | (**status:** `proposed`)

## Problem Statement

The user profile has no structured field for *what kind of taxpayer
this is*. The `overview` applicability engine therefore treats every
profile as an *autónomo en estimación directa* and gates individual
modelos only by a handful of suppression flags.

A landlord persona (Bernat,
`[[2026-05-21-persona-fleet-round3-findings]]`) whose only income is
*rendimientos del capital inmobiliario* hit the consequence directly:

- `overview agenda` / `calendar` / `explain 130` report **Modelo 130
  applicable and overdue** for him. He has no *actividad económica*
  and no Modelo 130 obligation at all. The tool gives wrong - and
  legally harmful - filing guidance.
- There is no field a pure landlord, a salaried-only employee, or a
  pensioner can set to declare "I have no economic activity", so the
  quarterly business modelos (130, 303, ...) cannot be gated out for
  them.

"What do I have to file?" is the most basic question a taxpayer asks.
The tool currently answers it wrong for every taxpayer who is not an
autónomo with an economic activity.

## Considerations

- **Taxpayer income type is a structured fact, not free text.** The
  profile's `activity` field is free text and drives no logic. Spanish
  IRPF distinguishes income categories - economic-activity income
  (autónomo), employment income, capital income (movable and
  immovable / rental), pensions, etc. A taxpayer's modelo obligations
  follow from which categories apply.
- **Applicability must derive from the taxpayer type.** Modelo 130 /
  303 follow from economic activity; Modelo 100 (Renta) applies to
  essentially every IRPF taxpayer; Modelo 115 is filed by the *payer*
  of rent under retention, not by a landlord receiving it. The
  applicability engine must compute from the declared income types,
  not assume autónomo.
- **The per-modelo rules are registry-grounded.** Which modelo applies
  to which taxpayer type, and the legal basis, is regulatory data -
  it belongs in the registry alongside the casilla and deadline data,
  carrying `legal_refs`. This ADR sets the *model and the derivation*;
  the registry carries the *rules and their grounding*.
- **Default must be safe.** With no income type declared, the engine
  must not silently assume autónomo and over-report obligations. A
  conservative default (or an explicit "income type not yet declared,
  applicability is incomplete" state) is safer than a confident wrong
  answer.

## Constraints

- The profile gains a structured, typed taxpayer income-type field
  (a typed model / enum set - not free text), expressing which IRPF
  income categories apply.
- Modelo applicability is DERIVED from the declared income types via
  registry-grounded rules; the autónomo-by-default assumption is
  removed.
- Per the calculation-grounding rule, the registry applicability
  rules carry `legal_refs`; no invented legal behaviour.
- The CLI must never present a confidently wrong "you must file X" -
  when the income type is undeclared, applicability is reported as
  incomplete, not as a definite obligation.
- Per the apex CLI ADR, the CLI root surface stays `config` / `app`;
  no new root verbs.

## Decision / Implementation

1. Add a structured **taxpayer income-type** to the profile schema -
   the set of IRPF income categories the taxpayer has (economic
   activity / professional, employment, immovable capital / rental,
   movable capital, pension, ...). It is a typed field, validated
   like the other profile facts.
2. The `overview` applicability engine derives each modelo's
   `applicable` verdict from the declared income types through
   registry applicability rules, replacing the autónomo default.
3. The wizard collects the income type at profile creation /edit, in
   plain operator language ("¿De dónde proceden tus ingresos?").
4. When the income type is undeclared, `overview` reports
   applicability as **incomplete** and points at the field to set -
   it never reports a definite obligation it cannot justify.
5. The per-modelo applicability rules and their `legal_refs` are
   registry data; populating them (and the missing Modelo 100 / 303 /
   347 deadline windows - round-3 finding R1) is sequenced with the
   registry track. A follow-up plan tracks the wiring.

## Rationale

A tax tool whose first answer - "what do I file?" - is wrong for
every non-autónomo taxpayer is not trustworthy. The cause is a
missing model: the profile never captures what kind of income the
taxpayer has, so the engine guesses, and guesses autónomo. Making the
income type an explicit, typed profile fact and deriving applicability
from it - through registry-grounded, `legal_refs`-carrying rules -
replaces a confident wrong answer with a correct one, or with an
honest "tell me your income type first". It also generalises cleanly
to salaried-only, pensioner, and mixed taxpayers.

## Consequences

- The wrong-filing-guidance defect class (Modelo 130 pushed at
  landlords / salaried / pensioners) is closed at its root.
- The profile schema gains a field; the wizard gains a step; the
  applicability engine is rewritten to derive rather than default.
- The registry must carry per-modelo applicability rules with
  `legal_refs`, and the missing Modelo 100 / 303 / 347 deadline
  windows must be registered - a registry-track dependency.
- This is a tax-semantics and schema decision; it is recorded
  `proposed` and should be confirmed by the project owner, and a
  follow-up plan should sequence the schema, engine, and registry
  work.
