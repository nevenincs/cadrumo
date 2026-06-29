---
tags:
  - '#audit'
  - '#cli-testimonial'
date: '2026-05-27'
modified: '2026-06-29'
related:
  - "[[2026-05-27-mateo-cli-testimonial-audit]]"
  - "[[2026-05-27-sergio-cli-testimonial-audit]]"
---

# `cli-testimonial` audit: `round-16 Olivia Whitfield UK pensioner non-resident M210`

## Scope

Sixteenth testimonial round, Olivia Whitfield — British retired
schoolteacher, Lytham St Annes (Lancashire). Spends 4 weeks/year
in Spain; UK tax resident. Inherited Málaga piso 2018, rents at
€820/month to particular tenant (vivienda habitual). Spanish-source
obligation: Modelo 210 (IRNR), Impuesto sobre la Renta de No
Residentes. Post-Brexit (UK = non-EU): 24% tipo over rendimiento
BRUTO without deductible gastos (TRLIRNR Art. 25.1.a general-rate
branch; EU/EEE deductibility is Art. 24.6). Convenio
España-UK BOE-A-2014-5171 governs double-taxation credit.

> 2026-06-29 legal-grounding update: this testimonial originally
> conflated TRLIRNR art. 25.1.f with the non-EU rental/general-rate
> path. Current law/corpus split is: art. 25.1.a supplies the 24%
> general rate and the qualifying EU/EEE 19% reduced general rate; art.
> 25.1.f supplies an unconditional 19% income-class rate for dividends,
> interest, and capital gains. Olivia's UK property-rental example
> remains a 24% gross-basis case, but under art. 25.1.a/art. 24, not
> art. 25.1.f.

First exercise of non-resident axis, M210, Brexit régimen, and
convenio aplicable. None previously tested.

## Findings

### CRITICAL — Modelo 210 (IRNR) entirely absent from registry

`aeat app modelo list` returns 29 modelos covering IRPF, IS, IVA,
patrimonio, informativos — but no M210. `aeat app modelo work
create --modelo 210` returns `Unknown modelo 210`.

M210 is the principal annual/quarterly form for non-residents with
Spanish-source income. Without it the CLI is wholly unusable for
~90,000 British nationals + ~200,000 other non-residents with
Spanish property income.

### CRITICAL — No non-resident taxpayer axis in profile model

Profile schema has only `--tax-residence-ccaa` (Spanish CCAA).
No `--tax-residence-status`, no `--country-of-residence`, no
flag indicating non-residency. The closest field
`--spouse-non-resident-irpf` applies only to spouse in IRPF
context.

Creating a profile without CCAA silently defaults to `madrid`.
A British pensioner is filed as Madrid resident — wrong
framework (IRPF instead of IRNR), wrong tipo, wrong gastos
deductibility, wrong submission body.

### CRITICAL — Brexit EU/non-EU distinction absent

Under TRLIRNR Art. 25.1.a, the general rate is 24% and the qualifying
EU/EEA reduced general-rate branch is 19%; Art. 24.6 is the separate
deductible-expense basis for qualifying EU/EEA residents. Post-Brexit
UK rental income remains outside that EU/EEA branch and faces 24% over
rendimiento BRUTO. Art. 25.1.f is not the non-EU rental/general-rate
authority; it is the unconditional 19% income-class rate for dividends,
interest, and capital gains.

Olivia's 2024 liability:
- Correct (non-EU, gross): 24% × €9,840 = €2,361.60.
- Wrong (EU-style, net): 19% × (€9,840 − €1,200 gastos) = €1,641.60.
Difference: €720/year per filer.

Profile has no `--ue-eee-status` or `--country-of-fiscal-residence`
to derive it. The existing spouse-side EU/EEA fields demonstrate
the framework knows the concept but doesn't apply it to the
primary taxpayer in IRNR context.

### HIGH — Representante fiscal not modelled

Art. 47 LGT + Art. 10 TRLIRNR require non-EU non-residents to
appoint a representante fiscal in Spain. The representante NIF
appears on M210. The CLI has no profile field, no M210 binding,
no prompt anywhere asking about representante. Olivia filing
M210 without representante NIF produces formally defective
declaración the AEAT can reject.

### HIGH — Convenio para evitar la doble imposición not modelled

Spain-UK convenio (BOE-A-2014-5171, in force 12 June 2014).
Art. 6: Spain primary taxing rights over Málaga rental. Art. 23:
UK must provide credit for Spanish tax paid. The CLI has no
`--convenio-aplicable`, no `--pais-residencia-convenio`, no
convenio article citations in M210 output, no `tax_paid
_certification` field for UK Self Assessment provenance.

Without convenio identification, Olivia cannot evidence the
Spanish tax paid when filing her UK Self Assessment — HMRC will
not grant the foreign tax credit without a certificate of tax
paid in Spain.

### HIGH — M100 silently accepted for non-resident profile

`aeat app modelo work create --modelo 100` on Olivia's profile
(silently defaulted to Madrid CCAA) succeeds without warning.
M100 (IRPF) applies only to Spanish fiscal residents (Art. 8
Ley 35/2006). A British pensioner filing M100 produces an
invalid declaración. False-positive pathway into wrong filing.

Once Finding "non-resident axis" lands, M100 must refuse for
`fiscal_residency = non_resident_irnr` without explicit override.

### MEDIUM — Retención Art. 31.4 TRLIRNR not surfaced

When tenant is a particular renting as vivienda habitual, no
retención applies. When tenant is a company or IRPF-obligated
profesional, 19% retención applies and offsets M210 liability.
The CLI has no M210 binding for `retenciones_a_cuenta_pagadas`
and no prompt asking whether retención applied. Olivia's case
(particular tenant) is fine but corporate-tenant cases would
produce wrong cuota diferencial.

### MEDIUM — Silent Madrid CCAA default re-confirmed

When CCAA omitted, profile silently assigns Madrid (already
flagged by Lourdes round-12 F8). For non-resident profiles the
field should be suppressed entirely, not default-populated.

### LOW — M210 should get M151-style graceful refusal at minimum

M151 (Beckham) currently produces a legally-grounded refusal
naming Art. 93 LIRPF and redirecting to AEAT Sede. M210 should
receive identical treatment: "Modelo 210 (IRNR — no residentes)
is not yet implemented. File directly at AEAT Sede:
sede.agenciatributaria.gob.es/Sede/procedimientoini/G320.shtml.
Legal authority: RD Leg 5/2004 (TRLIRNR)." Cheap defect-of-record
matching the M721/M714/M151/M650 pattern.

## Recommendations

Priority order:

1. **M210 Path-B refusal stub** (CRITICAL, low cost) — extend
   `_STUB_ONLY_MODELOS` to include `"210"`, scaffold locale keys
   citing RD Leg 5/2004 + AEAT Sede link. Closes the "Unknown
   modelo 210" silent-misrouting hazard immediately. Same shape
   as M721/M714/M151/M650.

2. **Non-resident profile axis** (CRITICAL, FOUNDATIONAL) — add
   `taxpayer_type.fiscal_residency: Literal["resident_irpf",
   "non_resident_irnr"]`, `country_of_fiscal_residence: str`
   (ISO 3166-1 alpha-2), derived `ue_eee_status: bool` from
   country code. Suppresses CCAA prompt when non-resident.
   Unlocks IRNR modelos; blocks IRPF modelos. Pattern parallel
   to Beckham régimen axis (#162) and pareja-de-hecho axis
   (#176).

3. **Brexit EU/non-EU branching** (CRITICAL) — derived from
   `country_of_fiscal_residence`. Drives M210 tipo (19% vs 24%)
   and gastos deductibility. Requires the axis above.

4. **Representante fiscal fields** (HIGH) — profile fields
   `representante_fiscal_nif` + `representante_fiscal_nombre`,
   M210 bindings, validation enforcing presence for non-EU
   non-residents.

5. **Convenio doble imposición** (HIGH) — profile field
   `convenio_aplicable` (derived from country-of-residence),
   surface in M210 calculation output, add tax-paid-certification
   record to filing.

6. **Block M100 for non-resident profile** (HIGH) — depends on
   the axis. Same shape as the foral CCAA refusal (#175).

7. **M210 full engine** (LARGE) — rendimiento inmobiliario
   casillas, tipo branching by EU/EEA status, gastos branch
   gated on EU/EEA status, retenciones a cuenta deduction
   path. Largest single piece; can follow stub for several
   weeks.

8. **Retención surface** (MEDIUM) — M210 binding for
   `retenciones_a_cuenta_pagadas`.

9. **M211 stub** (LOW) — non-resident bien-transmisión
   retención. Useful when Olivia ever sells. Same Path-B shape
   as M210 stub.

Quantitative impact: ~90,000 UK property-owners post-Brexit +
~150,000 other non-EU non-residents + ~200,000 EU non-residents
all silently misrouted. M210 is one of the highest non-resident-
facing filings in the AEAT system.
