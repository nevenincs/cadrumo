---
tags:
  - '#adr'
  - '#cli-workflow-redesign'
date: '2026-05-21'
modified: '2026-05-21'
related:
  - "[[2026-05-21-taxpayer-type-applicability-research]]"
  - "[[2026-05-21-persona-fleet-round3-findings-audit]]"
  - "[[2026-05-12-cli-workflow-redesign-adr]]"
  - "[[2026-05-21-work-verify-deadline-independence-adr]]"
---

# `cli-workflow-redesign` adr: `The profile carries a structured entity-type, tax-regime, and enrolment model; modelos, calendar, calculations, and rules derive from it` | (**status:** `accepted`)

## Problem Statement

The user profile has no structured field for *what kind of taxpayer
this is*. The `overview` applicability engine therefore treats every
profile as an *autónomo en estimación directa* and gates individual
modelos only by a few suppression flags.

A landlord persona (Bernat,
`[[2026-05-21-persona-fleet-round3-findings]]`) hit the consequence:
`overview agenda` / `calendar` / `explain 130` report **Modelo 130
applicable and overdue** for a taxpayer whose only income is
*rendimientos del capital inmobiliario* - he has no *actividad
económica* and no Modelo 130 obligation. The most basic question a
taxpayer asks - "what do I file?" - is answered wrong for everyone
who is not an autónomo with an economic activity.

The project owner confirmed the fix is needed and **broadened the
scope**: the taxpayer model is not just an IRPF income-type. The
recognised filing profile changes the modelos, the enrolment, the
calendar, the calculations, the brackets, and the special rules
across three independent axes:

1. **Entity type.** A *sociedad limitada* (or other recognised legal
   entity) is a different taxpayer from a natural person - it files
   corporate-tax modelos (e.g. Modelo 200), not the Renta (Modelo
   100), with its own calendar and rate schedule. Natural persons
   themselves split by income category (economic-activity / autónomo,
   professional, employment, immovable and movable capital, pension).
2. **Tax regime.** *Estimación directa* (normal and simplificada) and
   *estimación objetiva* (módulos) carry materially different rules,
   modelos, and calculations; the IVA regime varies likewise.
3. **Special enrolments.** Provisions attach to specific enrolments -
   notably the digital IVA ledgers / SII (Suministro Inmediato de
   Información), plus recargo de equivalencia, OSS/IOSS, and others.
   The owner explicitly noted the SII provisions are outside their
   own knowledge and need research grounding.

## Considerations

- **Taxpayer type is a structured fact, not free text.** The
  `activity` field is free text and drives no logic. Entity type,
  income categories, regime, and enrolments are each closed,
  enumerable facts.
- **Modelos / calendar / calculations / brackets all derive from it.**
  Applicability, the filing calendar, which calculation a modelo
  runs, the rate/bracket schedule, and special-rule activation must
  all be computed from the declared taxpayer model - not assumed.
- **The rules are registry-grounded.** Which modelo applies to which
  entity-type/regime, the calendars, brackets, and special-rule
  conditions are regulatory data and belong in the registry, each
  carrying `legal_refs`. This ADR fixes the *model and the
  derivation*; the registry carries the *rules and their grounding*.
- **The SII / digital-IVA-ledger axis needs research first.** Its
  provisions are not yet well enough understood to specify; it must
  be grounded in BOE/AEAT sources before its rules are encoded.
- **Default must be safe.** With the taxpayer model undeclared, the
  engine must report applicability as *incomplete*, never assume
  autónomo and over-report obligations.

## Constraints

- The profile gains a structured, typed taxpayer model with three
  axes - entity type, tax regime, and special enrolments - each a
  typed enum/model, not free text.
- Modelo applicability, the calendar, the calculation selection, the
  brackets, and special-rule activation are DERIVED from that model
  via registry-grounded rules. The autónomo-by-default assumption is
  removed.
- Per the calculation-grounding rule, every registry applicability /
  calendar / bracket / special-rule entry carries `legal_refs`; no
  invented legal behaviour. SII provisions are grounded in BOE/AEAT
  research before encoding.
- The CLI never presents a confidently wrong obligation; an
  undeclared taxpayer model yields an honest "incomplete".
- Per the apex CLI ADR, the CLI root surface stays `config` / `app`.

## Decision / Implementation

This is a multi-wave architecture stream, not a single change. The
direction is accepted; the work is sequenced through the vaultspec
pipeline:

1. **Research** (`vaultspec-research`) - ground the entity-type axis
   (sociedad limitada and other recognised forms; their modelos -
   200, etc. - calendars, and rate schedules), the regime axis
   (estimación directa normal/simplificada, estimación objetiva), and
   especially the **SII / digital IVA ledger** provisions, in BOE and
   AEAT sources.
2. **Schema** - add the typed three-axis taxpayer model (entity type,
   tax regime, special enrolments) to the profile schema, validated
   like the other profile facts; the wizard collects it in plain
   operator language.
3. **Derivation engine** - rewrite the `overview` applicability
   engine, and the calendar, calculation-selection, and bracket
   resolution, to derive from the taxpayer model through
   registry-grounded rules; remove the autónomo default.
4. **Registry rules** - populate the per-entity/per-regime
   applicability, calendar (including the missing Modelo 100/303/347
   deadline windows, round-3 finding R1), and bracket data, each with
   `legal_refs`.
5. Child ADRs are spawned where an axis needs its own adjudication
   (the corporate-entity calculation model and the SII model are the
   likely candidates). An evolving plan tracks the waves and audits.

## Rationale

A tax tool whose first answer - "what do I file?" - is wrong for
every taxpayer who is not an autónomo is not trustworthy, and the
divergence is not cosmetic: a company, a different regime, or an SII
enrolment changes the modelos, calendar, calculations, brackets, and
special rules wholesale. The cause is a missing model - the profile
never captures the taxpayer's entity type, regime, or enrolments, so
the engine guesses autónomo. Making those an explicit, typed,
registry-grounded model and deriving everything downstream from it
replaces a confident wrong answer with a correct one - or with an
honest "declare your taxpayer type first".

## Consequences

- The wrong-filing-guidance defect class is closed at its root, for
  landlords, salaried-only taxpayers, pensioners, companies, and
  every non-default regime.
- This is a substantial stream: profile schema, wizard, the
  applicability/calendar/calculation/bracket engines, and a body of
  registry rule data all change; child ADRs and an evolving plan are
  required.
- A hard dependency on the registry track: per-entity/per-regime
  rules and the missing deadline windows must be registered with
  `legal_refs`.
- **Owner decision (2026-05-21): accepted in direction.** The owner
  confirmed entity type, regime, and special enrolments all reshape
  the filing profile, and flagged SII as needing research. The ADR
  is `accepted`; implementation begins with the research phase -
  no schema or engine change lands before its rules are grounded.
