---
name: cadrumo-retenedor-empleador
description: >-
  Sequence the obligations of a taxpayer who withholds retención (salaries, professional
  fees, local rent): the quarterly retenciones self-assessments and their annual
  informativas, read from the overview calendar rather than assumed. Use when the
  profile declares `has_employees`, `pays_professionals_with_retencion` or
  `pays_rent_with_retencion` true.
applies_when:
  profile_match: any
  profile_facts:
    - fact: has_employees
      match: is_true
    - fact: pays_professionals_with_retencion
      match: is_true
    - fact: pays_rent_with_retencion
      match: is_true
---

# Retenedor / empleador

Gating predicate: the active `TaxpayerProfile` declares at least one of
`has_employees` (salaries with retención, LIRPF Arts. 99-101),
`pays_professionals_with_retencion` (professional-fee retención, LIRPF Art. 101.5), or
`pays_rent_with_retencion` (alquiler de local retención, LIRPF Art. 101.8). This is a
facts-driven overlay: a taxpayer routed here may simultaneously match
`cadrumo-autonomo-estimacion-directa`, `cadrumo-autonomo-modulos` or
`cadrumo-pyme-sociedad` on their entity-type or regime axis, and both skills'
obligations apply. This skill is thin: it sequences the retención-specific obligations
Cadrumo derives and points each filing to the modelo skill that owns it.

## Preconditions

- The taxpayer is onboarded (`cadrumo-alta-contribuyente` has run) and
  `aeat app overview status` reports an active profile.
- The profile declares at least one gating fact. If undeclared but suspected (the
  ledger shows salary or professional-fee payments), load `cadrumo-alta-contribuyente`
  to confirm before continuing.
- The taxpayer's primary regime skill already sequences the domestic IVA and income-tax
  obligations; do not duplicate that sequencing here.

## Procedure

Each overview command below is a local read of the profile and the bundled registry; it
never contacts the tax authority. Through the tool server, `search` for the operation,
`describe` it, run it with `execute` and read the outcome with `result`. Say what you
are about to read before you run it.

1. Derive the applicable obligations - never assume the retenciones obligation set from
   memory; the specific modelo depends on which retención type (labor, professional,
   rental) is in play. Read `aeat app overview calendar --from <PERIOD-START> --to
   <PERIOD-END>` (operation `overview.calendar`) and `aeat app overview agenda`
   (`overview.agenda`). Read any `coverage_advised` entry as an open question to put to
   the taxpayer.
2. Confirm each candidate modelo's applicability with `aeat app overview explain
   <MODELO> --year <YEAR>` (`overview.explain`): 111 for retenciones on labor and
   professional-fee income, 115 for rental retenciones. Read `verdict`, `rationale` and
   the `profile_facts` to confirm which retención types the profile actually declares
   rather than assuming all three.
3. List the modelos the registry models: tool `authority` with `query` `modelos`, or
   `aeat app modelo list` (a local read).
4. Sequence the itinerary:
   - The ledger must record every withheld payment with its retención category and rate
     before any calculation: load `cadrumo-llevar-libro`, then `cadrumo-clasificar`.
   - The quarterly retenciones self-assessments the calendar surfaces: load
     `cadrumo-preparar-modelo-111` (labor and professional fees) and
     `cadrumo-preparar-modelo-115` (rental).
   - The annual informativa the calendar surfaces: load `cadrumo-preparar-modelo-190`
     (summarising the year's Modelo 111 filings) or `cadrumo-preparar-modelo-180`
     (summarising Modelo 115), once the quarterly filings for the full year are
     complete.
5. After the taxpayer has filed in the AEAT portal, load `cadrumo-reconciliar` for that
   filing.

## Success assertions

- Every obligation acted on was read from `overview.calendar`, `overview.agenda` or
  `overview.explain`, never assumed from this skill's prose.
- A `coverage_advised` entry is surfaced to the taxpayer, not silently dropped - in
  particular, an annual informativa the deadline engine has not yet windowed is an open
  question, not evidence the taxpayer need not file it.
- No casilla value is computed here; every number is quoted from the output of the
  per-modelo skill's tools.

## Finish

Each filing follows its own skill through verify, export (only with the person's
go-ahead), the taxpayer's own filing and reconciliation. This skill is done once every
calendar-surfaced retención obligation for the period has been routed, alongside
whatever the taxpayer's primary regime skill already sequenced.
