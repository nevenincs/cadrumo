---
tags:
  - '#audit'
  - '#cli-testimonial'
date: '2026-05-27'
modified: '2026-05-27'
related:
  - "[[2026-05-27-aitor-cli-testimonial-audit]]"
  - "[[2026-05-27-lourdes-cli-testimonial-audit]]"
---

# `cli-testimonial` audit: `round-21 Marcos Salcedo first-home matrimonio sobrevenido conjunta`

## Scope

Twenty-first testimonial round, Marcos Salcedo Núñez — Madrid
software engineer 34, married Elena 22-March-2024, bought first
vivienda habitual Vallecas Aug-2024 (€295k, €245k mortgage), ITP
€4,200. Both salaried (Marcos €52k + Elena €38k). Exercises:
matrimonio sobrevenido axis, conjunta vs individual comparison,
vivienda habitual post-2013 deducción status, Modelo 600 ITP-AJD
autonomic routing.

## Findings

### HIGH — `--marriage-date` field missing from profile

Profile has `--marital-status 2` (married) but no `--marriage-date`
to capture exact date. Matrimonio sobrevenido (married mid-year)
requires casillas 0245 (married full year) vs 0246/0247 (first/last
month if partial year). The motor does not auto-derive these.

User must manually set `--casilla "0246=3" --casilla "0247=12"` to
indicate March-December marriage. A user setting 0245=1 silently
declares "married all year" when they were married only 9 months —
incorrect declaration.

Affects every taxpayer marrying mid-year (~80,000 weddings/year
in Spain).

### HIGH — Reducción conjunta Art. 84 LIRPF (€3,400) not auto-applied

Profile carries `filing_export.declaration_type = 2` (conjunta).
Casilla 0461 (Reducción para unidades familiares por tributación
conjunta) stays 0 across all calculate runs. Manual override
`--casilla "0461=3400"` works; motor applies correctly (BLG €52k
→ €48.6k). But not auto-derived.

A user declaring conjunta without knowing Art. 84 pays excess
cuota. Risk of erroneous declaration in user's disfavor — pattern
parallel to mínimo 65+ (#205) and Art. 81 monoparental (#188).

### HIGH — No conjunta vs individual comparison surface

For Marcos €52k + Elena €38k = €90k joint, the €3,400 reducción
typically does NOT compensate the progressive tariff bite. No
`aeat app modelo work compare-taxation` verb. No `--what-if`
flag. Users must manually create two separate work units
(individual A + individual B vs joint), calculate each, subtract
mentally.

AEAT's Renta Web includes a "simulador" for exactly this. CLI
should mirror.

### MEDIUM — Generic error on `profile create --taxation-type 2` without `--spouse-tax-id`

`Refused. La entrada del comando no superó la validación`. No
field-level diagnostic. Should explicitly say
"taxation-type=2 requires --spouse-tax-id". Pattern similar to
Lourdes F10 (DRAFT_HAS_ERRORS opaque).

### MEDIUM — Vivienda habitual post-2013 silently accepts deducción inputs

Marcos can populate casillas 0708-0714 (anexo A.1 vivienda
habitual deducción inputs) without warning that the deducción
itself is ELIMINATED for purchases post-31-Dec-2012 (Ley
16/2012). 0547/0548 remain zero correctly, but a user entering
mortgage interest expecting deducción gets silent no-op.

Surface a verification finding when 0708 (fecha adquisición)
post-2012 AND user populates 0712 (importe inversión) →
"Deducción inversión vivienda habitual eliminada para
adquisiciones posteriores al 31-12-2012 (Ley 16/2012). Solo
aplica el régimen transitorio DT 18ª LIRPF a adquisiciones
anteriores."

### MEDIUM — M600 error message generic

`Modelo desconocido 600` returned without explanation that M600
is autonomic (ITP-AJD), gestionado por Hacienda CCAA, not AEAT.
Should redirect like M651/M715/M721 stub messages.

### POSITIVE — Several elements work correctly

- NIF validation with proactive correction (`la letra debe ser Z`).
- Casillas 0246/0247 for matrimonio sobrevenido work
  mechanically (engine accepts them).
- M600 correctly absent (autonomic — not AEAT scope).
- Reducción Art. 84 calculus correct when 0461 manually entered.

## Recommendations

Priority order:

1. **`--marriage-date` + auto-derive 0245/0246/0247 (HIGH)** —
   add date field to profile schema; motor derives casillas from
   `(marriage_date.month, 12)` for the filing year.

2. **Auto-apply 0461 €3,400 from declaration_type=2 (HIGH)** —
   formula consults profile `declaration_type` and sets 0461.
   Add `aeat-dr-100-2024-dictionary` to host construct source_refs
   per FU-S353 pattern.

3. **Conjunta vs individual comparator (HIGH)** — new verb
   `aeat app modelo work compare-taxation` or
   `aeat app modelo work calculate --what-if individual` flag.

4. **Field-level diagnostic on profile validation (MEDIUM)** —
   improve refusal messages.

5. **Vivienda-habitual post-2013 advisory (MEDIUM)** —
   verification finding when 0708 fecha > 2012-12-31.

6. **M600 autonomic redirect (MEDIUM)** — pattern parallel to
   M651/M715 stubs but for the entire ITP-AJD family (M600,
   M620). Path-B refusal stub naming Hacienda CCAA + Ley 28/1990.

7. **(POLISH) M600/M620/M650/M660 stub bundle** — since these
   are all autonomic-managed informativas/autoliquidaciones with
   same redirect pattern, a single batch FU could cover them all.

This round is less dense in CRITICALs than several earlier
persona rounds, but the conjunta-vs-individual gap is
operationally important for ~200k newly-married Spanish couples
each year and the vivienda-habitual post-2013 silent acceptance
is a meaningful UX trap.
